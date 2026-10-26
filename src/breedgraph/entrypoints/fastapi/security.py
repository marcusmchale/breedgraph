from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse

from breedgraph.custom_exceptions import UnauthorisedOperationError
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from breedgraph.config import SECRET_KEY, CSRF_SALT, CSRF_EXPIRES, get_vue_url, cookie_name, cookie_path

import logging
logger = logging.getLogger(__name__)

router = APIRouter()


class CSRFTokenManager:
    """Shared utility for CSRF token generation and validation"""

    @staticmethod
    def generate_token() -> str:
        """Generate a new CSRF token"""
        ts = URLSafeTimedSerializer(SECRET_KEY)
        return ts.dumps('csrf_token', salt=CSRF_SALT)

    @staticmethod
    def set_token_cookie(response: Response, token: str) -> None:
        """
        Set CSRF token cookie on response: for this host only, as the login and acceptance cookies are, so that a
        site on a subdomain, such as a demonstration site, is never sent this one's; and, as they are, named with
        COOKIE_PREFIX for the site's path (cookie_path), so that one beside it on the same host keeps its own
        """
        response.set_cookie(
            key=cookie_name("csrf_token"),
            value=token,
            httponly=True,
            secure=True,
            samesite="strict",
            path=cookie_path(),
            max_age=CSRF_EXPIRES
        )

    @staticmethod
    def validate_token(token: str) -> bool:
        """Validate a CSRF token. Returns True if valid, raises exception if not."""
        ts = URLSafeTimedSerializer(SECRET_KEY)
        ts.loads(token, salt=CSRF_SALT, max_age=CSRF_EXPIRES)
        return True

@router.options("/csrf")
async def csrf_preflight():
    return Response(status_code=200)

@router.post("/csrf")
async def get_csrf_token(request: Request, response: Response):
    # Check if both tokens exist
    cookie_token = request.cookies.get(cookie_name("csrf_token"))
    header_token = request.headers.get("X-CSRF-Token")

    if cookie_token and header_token:
        try:
            # First check if tokens match
            if cookie_token != header_token:
                raise UnauthorisedOperationError("CSRF token mismatch")

            # Then verify the token
            CSRFTokenManager.validate_token(cookie_token)
            return {"token": cookie_token}
        except SignatureExpired:
            logger.debug("CSRF token has expired")
            # Generate new token if expired
            pass
        except BadSignature:
            logger.warning("Invalid CSRF token signature detected")
            # Generate new token if invalid
            pass
        except Exception as e:
            logger.error(f"Unexpected error validating CSRF token: {str(e)}")
            # Generate new token for any other error
            pass

    signed_token = CSRFTokenManager.generate_token()
    CSRFTokenManager.set_token_cookie(response, signed_token)
    return {"token": signed_token}

# NOTE! these need to be get requests so that the users can follow a link in their email.
@router.get("/verify")
async def verify_email(token: str):
    return RedirectResponse(url=f"{get_vue_url()}verify-email?token={token}")

@router.get("/reset")
async def reset_password(token: str):
    return RedirectResponse(url=f"{get_vue_url()}reset-password?token={token}")
