from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse

from src.breedgraph.custom_exceptions import UnauthorisedOperationError
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from src.breedgraph.config import SECRET_KEY, CSRF_SALT, CSRF_EXPIRES, HOST_ADDRESS, PROTOCOL, VUE_PORT

import logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.options("/csrf")
async def csrf_preflight():
    return Response(status_code=200)

@router.post("/csrf")
async def get_csrf_token(request: Request, response: Response):
    # Check if both tokens exist
    cookie_token = request.cookies.get("csrf_token")
    header_token = request.headers.get("X-CSRF-Token")

    if cookie_token and header_token:
        try:
            # First check if tokens match
            if cookie_token != header_token:
                raise UnauthorisedOperationError("CSRF token mismatch")

            # Then verify the token
            ts = URLSafeTimedSerializer(SECRET_KEY)
            ts.loads(cookie_token, salt=CSRF_SALT, max_age=CSRF_EXPIRES * 60)
            # If both checks pass, return the existing token
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

    # Generate new token
    ts = URLSafeTimedSerializer(SECRET_KEY)
    signed_token = ts.dumps(
        "csrf_token",
        salt=CSRF_SALT
    )
    response.set_cookie(
        key="csrf_token",
        value=signed_token,
        httponly=True,
        secure=True,
        samesite="strict",
        domain=HOST_ADDRESS,
        max_age=CSRF_EXPIRES * 60
    )
    return {"token": signed_token}

# NOTE! these need to be get requests so that the users can follow a link in their email.
@router.get("/verify")
async def verify_email(token: str):
    return RedirectResponse(url=f"{PROTOCOL}://{HOST_ADDRESS}:{VUE_PORT}/verify-email?token={token}")

@router.get("/reset")
async def reset_password(token: str):
    return RedirectResponse(url=f"{PROTOCOL}://{HOST_ADDRESS}:{VUE_PORT}/reset-password?token={token}")
