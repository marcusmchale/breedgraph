import inspect
from typing import Callable
from src.dbtools.adapters import redis_eventpublisher
from src.dbtools.adapters.notifications.notifications import AbstractNotifications, EmailNotifications
from src.dbtools.service_layer import event_handlers, command_handlers, messagebus, unit_of_work


def bootstrap(
        uow: unit_of_work.AbstractUnitOfWork = unit_of_work.Neo4jUnitOfWork(),
        notifications: AbstractNotifications = EmailNotifications(),
        publish: Callable = redis_eventpublisher.publish
) -> messagebus.MessageBus:
    dependencies = {'uow': uow, 'notifications': notifications, 'publish': publish}

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
