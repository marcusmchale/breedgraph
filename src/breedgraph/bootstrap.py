from asyncio import Queue

from breedgraph.service_layer.infrastructure.driver import AbstractAsyncDriver
from breedgraph.service_layer.infrastructure.unit_of_work import AbstractUnitOfWorkFactory
from breedgraph.service_layer.queries.views.views import AbstractViewsFactory
from breedgraph.service_layer.infrastructure.state_store import AbstractStateStore
from breedgraph.service_layer.infrastructure.notifications import AbstractNotifications
from breedgraph.service_layer.infrastructure.auth_service import AbstractAuthService

from breedgraph.service_layer.infrastructure.file_management import FileManagementService

from breedgraph.adapters.neo4j.driver import Neo4jAsyncDriver
from breedgraph.adapters.neo4j.unit_of_work import Neo4jUnitOfWorkFactory
from breedgraph.adapters.neo4j.views import Neo4jViewsFactory
from breedgraph.adapters.redis.state_store import RedisStateStore
from breedgraph.adapters.aiosmtp import EmailNotifications
from breedgraph.adapters.its_dangerous import ItsDangerousAuthService

from breedgraph.service_layer.handlers import handlers
from breedgraph.service_layer.messagebus import MessageBus


from typing import Type

import logging
logger = logging.getLogger(__name__)

async def bootstrap(
        driver: Type[AbstractAsyncDriver] = Neo4jAsyncDriver,
        uow_factory: Type[AbstractUnitOfWorkFactory] = Neo4jUnitOfWorkFactory,
        views_factory: Type[AbstractViewsFactory] = Neo4jViewsFactory,
        state_store: Type[AbstractStateStore] = RedisStateStore,
        notifications: Type[AbstractNotifications] = EmailNotifications,
        auth_service: Type[AbstractAuthService] = ItsDangerousAuthService,
        event_queue: Queue = Queue()
) -> MessageBus:
    logger.debug("Init driver")
    driver = driver()

    logger.debug("Init uow factory")
    uow_factory = uow_factory(driver=driver)

    logger.debug("Init state store")
    state_store = await state_store.create()

    logger.debug("Init views factory")
    views_factory = views_factory(driver=driver, state_store=state_store)

    logger.debug("Init notifications")
    notifications = notifications()

    logger.debug("Init auth service")
    auth_service = auth_service()

    logger.debug("Init file management service")
    file_management: FileManagementService = FileManagementService(state_store)

    handlers.register_dependencies(
        uow_factory=uow_factory,
        views_factory=views_factory,
        notifications=notifications,
        state_store=state_store,
        auth_service=auth_service,
        file_management=file_management,
        event_queue=event_queue
    )

    return MessageBus(
        uow_factory=uow_factory,
        views_factory=views_factory,
        state_store=state_store,
        auth_service=auth_service,
        file_management=file_management,
        event_handlers=handlers.event_handlers,
        command_handlers=handlers.command_handlers,
        event_queue=event_queue
    )
