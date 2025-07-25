from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from typing import Optional

from src.breedgraph import config
from src.breedgraph.custom_exceptions import UnauthorisedOperationError

import logging

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self):
        self._serializer = URLSafeTimedSerializer(config.SECRET_KEY)

    def create_token(self, user_id: int) -> str:
        """Create an authentication token for a user"""
        token = self._serializer.dumps(
            user_id,
            salt=config.LOGIN_SALT
        )
        return token

    def validate_token(self, token: str) -> Optional[int]:
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