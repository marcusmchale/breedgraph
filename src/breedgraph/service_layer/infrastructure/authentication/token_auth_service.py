from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from typing import Optional

from src.breedgraph import config
from src.breedgraph.custom_exceptions import UnauthorisedOperationError

from .auth_service import AbstractAuthService

import logging

logger = logging.getLogger(__name__)


class ItsDangerousAuthService(AbstractAuthService):
    def __init__(self):
        self._serializer = URLSafeTimedSerializer(config.SECRET_KEY)

    def create_login_token(self, user_id: int) -> str:
        """Create an authentication token for a user"""
        token = self._serializer.dumps(
            user_id,
            salt=config.LOGIN_SALT
        )
        return token

    def validate_login_token(self, token: str) -> Optional[int]:
        """Validate a token and return the user_id if valid"""
        if not token:
            return None

        try:
            return self._serializer.loads(
                token,
                salt=config.LOGIN_SALT,
                max_age=config.LOGIN_EXPIRES * 60
            )
        except SignatureExpired as e:
            logger.debug(f"Attempt to use expired token, signed: {e.date_signed}")
            raise UnauthorisedOperationError("The login token has expired")
        except BadSignature:
            logger.debug("Invalid token signature")
            return None

    def create_email_verification_token(self, user_id: int, email: str) -> str:
        """Create an email verification token containing user_id and email"""
        token = self._serializer.dumps(
            {'user_id': user_id, 'email': email},
            salt=config.VERIFY_TOKEN_SALT
        )
        return token

    def validate_email_verification_token(self, token: str) -> dict:
        """Validate an email verification token and return the data if valid"""
        if not token:
            raise UnauthorisedOperationError("Invalid verification token")

        try:
            return self._serializer.loads(
                token,
                salt=config.VERIFY_TOKEN_SALT,
                max_age=config.VERIFY_EXPIRES * 60
            )
        except SignatureExpired as e:
            logger.debug(f"Attempt to use expired token, signed: {e.date_signed}")
            raise UnauthorisedOperationError("This token has expired")
        except BadSignature:
            logger.debug("Invalid email verification token signature")
            raise UnauthorisedOperationError("Invalid verification token")


