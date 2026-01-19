import logging

from asyncio import Queue, create_task, gather, Task

from src.breedgraph.domain import commands, events
from src.breedgraph.config import N_EVENT_HANDLERS

#if TYPE_CHECKING:
from typing import Callable, Dict, List, Union, Type
from src.breedgraph.service_layer.infrastructure import (
    AbstractUnitOfWorkFactory,
    FileManagementService,
    AbstractStateStore,
    AbstractAuthService
)
from src.breedgraph.service_layer.queries.views.views import AbstractViewsFactory

Message = Union[commands.Command, events.Event]

logger = logging.getLogger(__name__)
logger.debug("Messagebus ready")

#  - Commands are handled consecutively (though still async)
#  - Events are handled concurrently (asyncio)

class MessageBus:

    def __init__(
            self,
            uow: AbstractUnitOfWorkFactory,
            views: AbstractViewsFactory,
            state_store: AbstractStateStore,
            auth_service: AbstractAuthService,
            file_management: FileManagementService,
            event_handlers: Dict[Type[events.Event], List[Callable]],
            command_handlers: Dict[Type[commands.Command], Callable]
    ):
        self.uow = uow
        self.views = views
        self.state_store = state_store
        self.auth_service = auth_service
        self.file_management = file_management
        self.event_handlers = event_handlers
        self.command_handlers = command_handlers
        self.event_queue = Queue()

        self._workers: List[Task] = []
        self._started = False

    async def start(self):
        """Start the event processing workers. Call once at application startup."""
        if self._started:
            return
        self._started = True
        for _ in range(N_EVENT_HANDLERS):
            self._workers.append(create_task(self.handle_event()))

    async def stop(self):
        """Gracefully stop workers. Call at application shutdown."""
        await self.event_queue.join()  # Wait for pending events
        for task in self._workers:
            task.cancel()
        await gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        self._started = False


    async def handle(self, message: Message):
        result = None
        if isinstance(message, commands.Command):
            result = await self.handle_command(message)
        elif isinstance(message, events.Event):
            await self.event_queue.put(message)
        else:
            raise Exception(f'Not an Event or Command: {message}')

        return result

    async def handle_command(self, command: commands.Command):
        try:
            logger.info(command.__class__.__name__)
            logger.debug(command)
            handler = self.command_handlers[type(command)]
            if not handler:
                logger.debug(f"Command {type(command)} has no handler")
                return None
            else:
                result = await handler(command)
                for event in self.uow.collect_events():
                    await self.event_queue.put(event)
                return result
        except Exception as e:
            logger.error(e)
            raise

    async def handle_event(self):
        while True:
            event = await self.event_queue.get()
            handlers = self.event_handlers.get(type(event))
            if not handlers:
                logger.debug(f"Event {type(event)} has no handler")
            for handler in handlers or []:
                try:
                    logger.info(event.__class__.__name__)
                    logger.debug(event)
                    await handler(event)
                except Exception as e:
                    logger.error(e)
                    continue
            for e in self.uow.collect_events():
                await self.event_queue.put(e)
            self.event_queue.task_done()
