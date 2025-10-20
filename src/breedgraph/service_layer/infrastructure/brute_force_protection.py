import logging
import redis.asyncio as redis

from src.breedgraph.config import get_redis_host_and_port

logger = logging.getLogger(__name__)


class BruteForceProtectionService:
    """
    Service to protect against brute force login attempts.
    Uses Redis to track failed login attempts per username/IP.
    """

    def __init__(self, redis_client: redis.Redis, max_attempts: int = 5, lockout_duration: int = 300):
        """
        Args:
            redis_client: Redis connection
            max_attempts: Maximum failed attempts before lockout (default: 5)
            lockout_duration: Lockout duration in seconds (default: 300 = 5 minutes)
        """
        self.redis = redis_client
        self.max_attempts = max_attempts
        self.lockout_duration = lockout_duration

    @classmethod
    async def create(
            cls,
            connection: redis.Redis | None = None,
            max_attempts: int = 5,
            lockout_duration: int = 300,
            db: int = 0
    ) -> 'BruteForceProtectionService':
        """
        Create a new BruteForceProtectionService with its own Redis connection.

        Args:
            connection: Redis connection
            max_attempts: Maximum failed attempts before lockout
            lockout_duration: Lockout duration in seconds
            db: Redis database number (default: 1, separate from read model which uses 0)
        """
        if connection is None:
            logger.debug(f"Creating BruteForceProtectionService with Redis db={db}")
            host, port = get_redis_host_and_port()
            connection = await redis.Redis(host=host, port=port, db=db)
            logger.debug(f"Ping redis successful: {await connection.ping()}")

        return cls(connection, max_attempts, lockout_duration)


    async def is_locked_out(self, identifier: str) -> bool:
        """
        Check if an identifier (username or IP) is currently locked out.

        Args:
            identifier: Username or IP address to check

        Returns:
            True if locked out, False otherwise
        """
        key = f"login_lockout:{identifier}"
        return await self.redis.exists(key) > 0

    async def get_remaining_attempts(self, identifier: str) -> int:
        """
        Get the number of remaining login attempts before lockout.

        Args:
            identifier: Username or IP address

        Returns:
            Number of remaining attempts
        """
        key = f"login_attempts:{identifier}"
        attempts = await self.redis.get(key)
        if attempts is None:
            return self.max_attempts
        return max(0, self.max_attempts - int(attempts))

    async def record_failed_attempt(self, identifier: str) -> None:
        """
        Record a failed login attempt and potentially trigger lockout.

        Args:
            identifier: Username or IP address
        """
        attempts_key = f"login_attempts:{identifier}"
        lockout_key = f"login_lockout:{identifier}"

        # Increment attempts counter with 1 hour expiry
        attempts = await self.redis.incr(attempts_key)
        await self.redis.expire(attempts_key, 3600)

        logger.debug(f"Failed login attempt for {identifier}: {attempts}/{self.max_attempts}")

        # If max attempts reached, set lockout
        if attempts >= self.max_attempts:
            await self.redis.setex(lockout_key, self.lockout_duration, "1")
            logger.warning(f"Login lockout triggered for {identifier}")

    async def record_successful_attempt(self, identifier: str) -> None:
        """
        Clear failed attempts counter on successful login.

        Args:
            identifier: Username or IP address
        """
        attempts_key = f"login_attempts:{identifier}"
        await self.redis.delete(attempts_key)
        logger.debug(f"Cleared failed attempts for {identifier}")

    async def get_lockout_ttl(self, identifier: str) -> int | None:
        """
        Get remaining lockout time in seconds.

        Args:
            identifier: Username or IP address

        Returns:
            Remaining seconds, or None if not locked out
        """
        key = f"login_lockout:{identifier}"
        ttl = await self.redis.ttl(key)
        return ttl if ttl > 0 else None