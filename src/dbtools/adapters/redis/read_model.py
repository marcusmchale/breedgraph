import logging

logger = logging.getLogger(__name__)

import redis.asyncio as redis

from src.dbtools.config import get_redis_host_and_port
from src.dbtools.domain.model.accounts import TeamInput, TeamStored


class ReadModel:
    def __init__(self, connection: redis.Redis):
        self.connection = connection

    @classmethod
    async def create(cls):
        logger.debug("Get redis connection")
        host, port = get_redis_host_and_port()
        connection = await redis.Redis(host=host, port=port)
        logger.debug(f"Ping redis successful: {await connection.ping()}")
        return cls(connection)

    async def add_email(self, email: str):
        logger.info(f"Adding allowed email: {email}")
        await self.connection.lpush("allowed_emails_list", email)
        await self.connection.sadd("allowed_emails", email)

    async def remove_email(self, email: str):
        logger.info(f"Removing allowed email: {email}")
        await self.connection.lrem("allowed_emails_list", 1, email)
        if await self.connection.lrem("allowed_emails_list", 1, email):
            await self.connection.lpush("allowed_emails", email)
        else:
            await self.connection.srem("allowed_emails", email)

    async def is_allowed_email(self, email: str):
        logger.info(f"Checking allowed email: {email}")
        return bool(await self.connection.sismember("allowed_emails", email))

    async def add_team(self, team: TeamInput):
        logger.info(f"Adding team: {team.json()}")
        await self.connection.sadd("teams", team.json())

    async def remove_team(self, team: TeamStored):
        logger.info(f"Removing team: {team.json()}")
        await self.connection.srem("teams", team.json())

    async def get_teams(self):
        logger.info(f"Getting teams")
        return await self.connection.smembers("teams")
