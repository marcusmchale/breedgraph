import redis.asyncio as redis
import src.breedgraph.adapters.neo4j.unit_of_work
from src.breedgraph.service_layer.infrastructure.notifications import AbstractNotifications
from src.breedgraph.adapters.aiosmtp import EmailNotifications

from src.breedgraph.service_layer.handlers import handlers
from src.breedgraph.service_layer import messagebus
from src.breedgraph.service_layer.infrastructure import (
    unit_of_work,
    AbstractAuthService,
    ItsDangerousAuthService,
    BruteForceProtectionService
)
from src.breedgraph.adapters.redis.read_model import ReadModel

from src.breedgraph.config import get_redis_host_and_port

import logging
logger = logging.getLogger(__name__)


async def bootstrap(
        uow: unit_of_work.AbstractUnitOfWork = src.breedgraph.adapters.neo4j.unit_of_work.Neo4jUnitOfWork(),
        notifications: AbstractNotifications = EmailNotifications(),
        auth_service: AbstractAuthService = ItsDangerousAuthService()
) -> messagebus.MessageBus:
    # Create a single Redis connection to be shared
    logger.debug("Creating shared Redis connection")
    host, port = get_redis_host_and_port()
    redis_connection = await redis.Redis(host=host, port=port, db=0)
    logger.debug(f"Ping redis successful: {await redis_connection.ping()}")

    read_model = await ReadModel.create(uow=uow)
    handlers.register_dependencies(
        uow=uow,
        notifications=notifications,
        read_model=read_model,
        auth_service=auth_service
    )

    return messagebus.MessageBus(
        uow=uow,
        read_model=read_model,
        event_handlers=handlers.event_handlers,
        command_handlers=handlers.command_handlers
    )
