import logging

import aioredis
from aioredis import Redis
from src.dbtools.config import get_redis_host_and_port

from src.dbtools.domain.model.accounts import Team

logger = logging.getLogger(__name__)


class ReadModel:
    def __init__(self, redis: Redis):
        self.redis = redis

    @classmethod
    async def create(cls):
        return cls(await aioredis.create_redis_pool(get_redis_host_and_port()))

    async def add_email(self, email: str):
        logger.info(f"Adding allowed email: {email}")
        await self.redis.lpush("allowed_emails_list", email)
        await self.redis.sadd("allowed_emails", email)

    async def remove_email(self, email: str):
        logger.info(f"Removing allowed email: {email}")
        await self.redis.lrem("allowed_emails_list", 1, email)
        if await self.redis.lrem("allowed_emails_list", 1, email):
            await self.redis.lpush("allowed_emails", email)
        else:
            await self.redis.srem("allowed_emails", email)

    async def is_allowed_email(self, email: str):
        logger.info(f"Checking allowed email: {email}")
        return bool(await self.redis.sismember("allowed_emails", email))

    async def add_team(self, team: Team):
        logger.info(f"Adding team: {team.json()}")
        await self.redis.sadd("teams", team.json())

    async def remove_team(self, team: Team):
        logger.info(f"Removing team: {team.json()}")
        await self.redis.srem("teams", team.json())

    async def get_teams(self):
        logger.info(f"Getting teams")
        return await self.redis.smembers("teams")
