import csv
import json
import redis.asyncio as redis

from src.breedgraph.config import get_redis_host_and_port
from src.breedgraph.domain.model.regions import LocationInput, LocationStored
from src.breedgraph.adapters.redis.load_data import RedisLoader

from src.breedgraph.service_layer.infrastructure import AbstractUnitOfWork

import logging
logger = logging.getLogger(__name__)

from typing import List, AsyncGenerator

class ReadModel:
    def __init__(self, connection: redis.Redis):
        self.connection = connection

    @classmethod
    async def create(
            cls,
            uow: AbstractUnitOfWork,
            connection: redis.Redis|None = None,
            db: int = 0) -> 'ReadModel':
        if connection is None:
            logger.debug(f"Create new redis connection for db = {db}")
            host, port = get_redis_host_and_port()
            connection = await redis.Redis(host=host, port=port, db=db)
            logger.debug(f"Ping redis successful: {await connection.ping()}")
        if not await connection.exists("country"):
            loader = RedisLoader(connection, uow)
            await loader.load_read_model()

        return cls(connection)

    #async def add_country(self, country: LocationInput) -> None:
    #    logger.info(f"Add country: {country}")
    #    await self.connection.sadd("country", country.json())
    #
    #async def remove_country(self, country: LocationStored) -> None:
    #    logger.info(f"Removing country: {country.json()}")
    #    await self.connection.srem("country", country.json())

    async def get_country(self, code: str) -> LocationInput|LocationStored|None:
        return self.connection.hget('country', code)

    async def get_countries(self) -> AsyncGenerator[LocationInput|LocationStored, None]:
        logger.info(f"Getting countries")
        countries_bytes = await self.connection.hgetall("country")
        for code, country in countries_bytes.items():
            country_json = json.loads(country)
            if country_json.get('id'):
                yield LocationStored(**country_json)
            else:
                yield LocationInput(**country_json)

    #async def add_email(self, email: str):
    #    logger.info(f"Adding allowed email: {email}")
    #    await self.connection.lpush("allowed_emails_list", email)
    #    await self.connection.sadd("allowed_emails", email)
    #
    #async def remove_email(self, email: str):
    #    logger.info(f"Removing allowed email: {email}")
    #    await self.connection.lrem("allowed_emails_list", 1, email)
    #    if await self.connection.lrem("allowed_emails_list", 1, email):
    #        await self.connection.lpush("allowed_emails", email)
    #    else:
    #        await self.connection.srem("allowed_emails", email)
    #
    #async def is_allowed_email(self, email: str):
    #    logger.info(f"Checking allowed email: {email}")
    #    return bool(await self.connection.sismember("allowed_emails", email))
