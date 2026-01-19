from abc import ABC, abstractmethod
from typing import Optional


class AbstractAuthService(ABC):

    @abstractmethod
    def create_login_token(self, user_id: int) -> str:
        """Create an authentication token for a user"""
        pass

    @abstractmethod
    def validate_login_token(self, token: str) -> Optional[int]:
        """Validate a token and return the user_id if valid, None if invalid"""
        pass

    @abstractmethod
    def create_email_verification_token(self, user_id: int, email: str) -> str:
        """Create an email verification token containing user_id and email"""
        pass

    @abstractmethod
    def validate_email_verification_token(self, token: str) -> dict:
        """Validate an email verification token and return the data if valid"""
        pass
