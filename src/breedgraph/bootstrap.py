import src.breedgraph.adapters.neo4j.unit_of_work

from src.breedgraph.service_layer.infrastructure.notifications import AbstractNotifications
from src.breedgraph.service_layer.infrastructure.file_management import FileManagementService
from src.breedgraph.service_layer.infrastructure.state_store import AbstractStateStore
from src.breedgraph.adapters.aiosmtp import EmailNotifications

from src.breedgraph.service_layer.handlers import handlers
from src.breedgraph.service_layer import messagebus
from src.breedgraph.service_layer.infrastructure import (
    unit_of_work,
    AbstractAuthService,
    ItsDangerousAuthService
)
from src.breedgraph.adapters.redis.state_store import RedisStateStore

import logging
logger = logging.getLogger(__name__)


async def bootstrap(
        uow: unit_of_work.AbstractUnitOfWork = src.breedgraph.adapters.neo4j.unit_of_work.Neo4jUnitOfWork(),
        notifications: AbstractNotifications = EmailNotifications(),
        auth_service: AbstractAuthService = ItsDangerousAuthService(),
        state_store: AbstractStateStore = RedisStateStore
) -> messagebus.MessageBus:

    state_store = await state_store.create(uow=uow)
    file_management: FileManagementService = FileManagementService(state_store)

    handlers.register_dependencies(
        uow=uow,
        notifications=notifications,
        state_store=state_store,
        auth_service=auth_service,
        file_management=file_management
    )

    return messagebus.MessageBus(
        uow=uow,
        state_store=state_store,
        file_management=file_management,
        event_handlers=handlers.event_handlers,
        command_handlers=handlers.command_handlers
    )
