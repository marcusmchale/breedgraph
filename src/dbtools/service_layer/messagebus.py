import logging
from asyncio import Queue, create_task, gather

from src.dbtools.domain import commands, events
from src.dbtools.config import N_EVENT_HANDLERS

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import Callable, Dict, List, Union, Type
    Message = Union[commands.Command, events.Event]
    from src.dbtools.service_layer.unit_of_work import AbstractUnitOfWork
    from src.dbtools.adapters.redis.read_model import ReadModel
    from concurrent.futures import ThreadPoolExecutor


logger = logging.getLogger(__name__)


#  - Commands are handled consecutively (though still async)
#  - Events are handled concurrently (asyncio)
class MessageBus:

    def __init__(
            self,
            uow: "AbstractUnitOfWork",
            read_model: "ReadModel",
            thread_pool: "ThreadPoolExecutor",
            event_handlers: "Dict[Type[events.Event], List[Callable]]",
            command_handlers: "Dict[Type[commands.Command], Callable]"
    ):
        self.uow = uow
        self.read_model = read_model
        self.thread_pool = thread_pool
        self.event_handlers = event_handlers
        self.command_handlers = command_handlers
        self.event_queue = Queue()  # currently just using asyncio for event queue,
        # todo consider scaling queue up to use redis as an event store

    async def handle(self, message: "Message"):
        if isinstance(message, commands.Command):
            await self.handle_command(message)
        elif isinstance(message, events.Event):
            await self.event_queue.put(message)
            # see https://docs.python.org/3/library/asyncio-queue.html for event queue design
            tasks = []
            for i in range(N_EVENT_HANDLERS):  # start concurrent event handlers
                tasks.append = create_task(self.handle_event())
            await self.event_queue.join()  # wait till no new events emerge
            for task in tasks:  # kill the event handlers
                task.cancel()
            # and wait till they are cancelled
            await gather(*tasks, return_exceptions=True)
        else:
            raise Exception(f'Not an Event or Command: {message}')

    async def handle_command(self, command: commands.Command):
        try:
            logger.info(command.__name__)
            logger.debug(command)
            handler = self.command_handlers[type(command)]
            await handler(command)
            for event in self.uow.collect_events():
                await self.event_queue.put(event)
        except Exception as e:
            logger.error(e)
            raise

    async def handle_event(self):
        while True:
            event = await self.event_queue.get()
            for handler in self.event_handlers[type(event)]:
                try:
                    logger.info(event.__name__)
                    logger.debug(event)
                    await handler(event)
                except Exception as e:
                    logger.error(e)
                    continue
            for e in self.uow.collect_events():
                await self.event_queue.put(e)
            event.task_done()
