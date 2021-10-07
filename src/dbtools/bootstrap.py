import inspect
from src.dbtools.adapters.notifications.notifications import AbstractNotifications, EmailNotifications
from src.dbtools.service_layer import event_handlers, command_handlers, messagebus, unit_of_work
from src.dbtools.config import MAX_WORKERS
from src.dbtools.adapters.redis.read_model import ReadModel
from concurrent.futures import ThreadPoolExecutor


async def bootstrap(
        uow: unit_of_work.AbstractUnitOfWork = unit_of_work.Neo4jUnitOfWork(),
        notifications: AbstractNotifications = EmailNotifications()
) -> messagebus.MessageBus:

    # todo consider mocking read model and passing into bootstrap for testing as for uow and notifications
    read_model = await ReadModel.create()
    thread_pool: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

    dependencies = {'uow': uow, 'notifications': notifications, 'read_model': read_model}

    injected_event_handlers = {
        event_type: [
            inject_dependencies(handler, dependencies)
            for handler in handlers
        ]
        for event_type, handlers in event_handlers.EVENT_HANDLERS.items()
    }
    injected_command_handlers = {
        command_type: inject_dependencies(handler, dependencies)
        for command_type, handler in command_handlers.COMMAND_HANDLERS.items()
    }

    return messagebus.MessageBus(
        uow=uow,
        read_model=read_model,
        thread_pool=thread_pool,
        event_handlers=injected_event_handlers,
        command_handlers=injected_command_handlers
    )


def inject_dependencies(handler, dependencies):
    params = inspect.signature(handler).parameters
    deps = {
        name: dependency
        for name, dependency in dependencies.items()
        if name in params
    }
    return lambda message: handler(message, **deps)
