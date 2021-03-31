import logging
from asyncio import Queue, create_task, gather
from dbtools.service_layer.unit_of_work import AbstractUnitOfWork

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import Callable, Dict, List, Union, Type
    from dbtools.domain import commands, events
    Message = Union[commands.Command, events.Event]


N_EVENT_HANDLERS = 3


#  - Commands are handled consecutively (though still async)
#  - Events are handled concurrently (asyncio)
class MessageBus:

    def __init__(
            self,
            uow: AbstractUnitOfWork,
            event_handlers: Dict[Type[events.Event], List[Callable]],
            command_handlers: Dict[Type[commands.Command], Callable],
    ):
        self.uow = uow
        self.event_handlers = event_handlers
        self.command_handlers = command_handlers
        self.event_queue = Queue()

    async def handle(self, message: Message):
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
            logging.debug(f'handling command {command}')
            handler = self.command_handlers[type(command)]
            await handler(command)
            for e in self.uow.collect_events():
                await self.event_queue.put(e)
        except Exception as e:
            logging.exception(command)
            logging.exception(e)
            raise

    async def handle_event(self):
        while True:
            event = await self.event_queue.get()
            for handler in self.event_handlers[type(event)]:
                try:
                    logging.debug(f'handling event {event}')
                    await handler(event)
                except Exception as e:
                    logging.exception(event)
                    logging.exception(e)
                    continue
            for e in self.uow.collect_events():
                await self.event_queue.put(e)
            event.task_done()

