from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from itsdangerous import URLSafeTimedSerializer, SignatureExpired

from .security import CSRFTokenManager
from src.breedgraph.config import (
    ENVIRONMENT,
    SECRET_KEY,
    CSRF_SALT,
    CSRF_EXPIRES,
    GQL_API_PATH,
    get_vue_url,
    Environment

)


import logging
logger = logging.getLogger(__name__)

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        logger.debug("==== Request Debug Info ====")
        logger.debug(f"URL: {request.url}")
        logger.debug(f"Method: {request.method}")
        logger.debug(f"Headers: {request.headers}")
        logger.debug(f"Cookies: {request.cookies}")
        # Get raw body for debugging
        body = await request.body()
        logger.debug(f"Body: {body.decode()}")
        logger.debug("========================")

        response = await call_next(request)
        return response


class CSRFMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, csrf_token_header: str = "X-CSRF-Token",
                 csrf_token_cookie: str = "csrf_token"):
        super().__init__(app)
        self.csrf_token_header = csrf_token_header
        self.csrf_token_cookie = csrf_token_cookie

    async def dispatch(self, request: Request, call_next):
        logger.debug(f"Request path: {request.url.path}")  # Add this debug line
        # Skip CSRF check for OPTIONS requests and the token endpoint itself
        if (
            request.method == "OPTIONS" or  # for preflight request
            request.url.path == "/csrf" or  # to retrieve cookie
            request.url.path == "/" or  # to allow redirect
            request.url.path == "/verify" or # to allow user registration, requires a token anyway
            request.url.path == "/reset" or # to allow users to reset password, requires a token anyway
            request.url.path == "/download"  # to allow users to download files, requires a token anyway
        ):
            return await call_next(request)

        # Validate CSRF tokens
        cookie_token = request.cookies.get(self.csrf_token_cookie)
        header_token = request.headers.get(self.csrf_token_header)

        if not cookie_token or not header_token:
            logger.debug("CSRF token missing - attempt to provide a new token")
            new_token = CSRFTokenManager.generate_token()
            response = Response(
                content='{"detail":"CSRF token missing - new token provided"}',
                status_code=403,
                headers={"X-CSRF-Token": new_token}
            )
            CSRFTokenManager.set_token_cookie(response, new_token)
            response.headers[self.csrf_token_header] = new_token
            return response
        try:
            if cookie_token != header_token:
                raise HTTPException(status_code=403, detail="CSRF token mismatch")

            CSRFTokenManager.validate_token(cookie_token)

        except (SignatureExpired, HTTPException):
            logger.info("CSRF token expired")
            new_token = CSRFTokenManager.generate_token()
            response = Response(
                content='{"detail":"CSRF token missing - new token provided"}',
                status_code=403,
                headers={"X-CSRF-Token": new_token}
            )
            CSRFTokenManager.set_token_cookie(response, new_token)
            response.headers[self.csrf_token_header] = new_token
            return response
        except Exception as e:
            logger.exception("CSRF validation failed")
            raise HTTPException(status_code=403, detail="Invalid CSRF token")

        response = await call_next(request)
        return response

def setup_middlewares(app: FastAPI) -> None:
    """Configure all middleware for the application"""
    # handy for debugging, note this breaks with file uploads
    #app.add_middleware(RequestLoggingMiddleware)

    origins = [get_vue_url().rstrip('/')]
    logger.debug(f"Setting up CORS middleware with origins: {origins}")
    # Setup CSRF
    app.add_middleware(
        CSRFMiddleware,
        csrf_token_header="X-CSRF-Token",
        csrf_token_cookie="csrf_token"
    )
    # Setup CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-CSRF-Token"]
    )


