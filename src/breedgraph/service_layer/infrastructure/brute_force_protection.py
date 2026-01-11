import logging
from operator import truediv

from src.breedgraph.service_layer.infrastructure.state_store import AbstractStateStore

logger = logging.getLogger(__name__)


class BruteForceProtectionService:
    """
    Service to protect against brute force login attempts.
    Uses the state store to track failed login attempts per username/IP.
    """

    def __init__(self, state_store: AbstractStateStore, max_attempts: int = 5, lockout_duration: int = 300):

        self.state_store = state_store
        self.max_attempts = max_attempts
        self.lockout_duration = lockout_duration

    async def is_locked_out(self, identifier: str) -> bool:
        """
        Check if an identifier (username or IP) is currently locked out.

        Args:
            identifier: Username or IP address to check

        Returns:
            True if locked out, False otherwise
        """
        if await self.get_lockout_ttl(identifier):
            return True
        else:
            return False

    async def record_failed_attempt(self, identifier: str) -> None:
        """
        Record a failed login attempt and potentially trigger lockout.

        Args:
            identifier: Username or IP address
        """
        attempts = await self.state_store.record_failed_login(identifier, 3600)
        if attempts > self.max_attempts:
            logger.warning(f"Login lockout triggered for {identifier}")
            await self.state_store.set_locked_out(identifier, self.lockout_duration)

    async def record_successful_attempt(self, identifier: str) -> None:
        """
        Clear failed attempts counter on successful login.

        Args:
            identifier: Username or IP address
        """
        await self.state_store.record_successful_login(identifier)

    async def get_lockout_ttl(self, identifier: str) -> int | None:
        """
        Get remaining lockout time in seconds.

        Args:
            identifier: Username or IP address

        Returns:
            Remaining seconds, or None if not locked out
        """
        ttl = await self.state_store.get_lockout_ttl(identifier)
        return ttl if ttl > 0 else None