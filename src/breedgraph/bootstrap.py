import src.breedgraph.adapters.neo4j.unit_of_work
from src.breedgraph.service_layer.infrastructure.notifications import AbstractNotifications
from src.breedgraph.adapters.aiosmtp import EmailNotifications

from src.breedgraph.service_layer.handlers import handlers
from src.breedgraph.service_layer import messagebus
from src.breedgraph.service_layer.infrastructure import unit_of_work, AbstractUnitOfWork, AbstractAuthService, ItsDangerousAuthService
from src.breedgraph.adapters.redis.read_model import ReadModel

async def bootstrap(
        uow: unit_of_work.AbstractUnitOfWork = src.breedgraph.adapters.neo4j.unit_of_work.Neo4jUnitOfWork(),
        notifications: AbstractNotifications = EmailNotifications(),
        auth_service: AbstractAuthService = ItsDangerousAuthService()
) -> messagebus.MessageBus:
    # todo mock read model and pass into bootstrap for testing as for uow and notifications
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
