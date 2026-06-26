from abc import ABC, abstractmethod
from contextlib import asynccontextmanager, AbstractAsyncContextManager

from breedgraph.domain.events import Event

from breedgraph.service_layer.repositories import AbstractRepoHolder
from breedgraph.service_layer.infrastructure.constraints import AbstractConstraintsHandler
from breedgraph.service_layer.application.access_control import AbstractAccessControlService
from breedgraph.service_layer.application import OntologyApplicationService, GermplasmApplicationService

from breedgraph.service_layer.infrastructure.driver import AbstractAsyncDriver

from typing import AsyncGenerator, Callable, Awaitable, Iterable, TYPE_CHECKING

import logging
logger = logging.getLogger(__name__)

EventPublisher = Callable[[Event], Awaitable[None]]

class AbstractUnitHolder(ABC):

    constraints: AbstractConstraintsHandler
    controls: AbstractAccessControlService
    ontology: OntologyApplicationService
    germplasm: GermplasmApplicationService
    repositories: AbstractRepoHolder
    committed: bool = False

    def collect_events(self) -> Iterable[Event]:
        ...

    @abstractmethod
    async def commit(self):
        ...

    @abstractmethod
    async def rollback(self):
        ...


class AbstractUnitOfWorkFactory(ABC):

    def __init__(self, driver: AbstractAsyncDriver):
        super().__init__()
        self.driver = driver
        self.event_publisher: EventPublisher|None = None

    def set_event_publisher(self, event_publisher: EventPublisher|None):
        self.event_publisher = event_publisher

    @asynccontextmanager
    async def get_uow(
            self,
            user_id: int|None = None,
            redacted: bool = True
    ) -> AsyncGenerator[AbstractUnitHolder, None]:
        async with self._get_uow(user_id=user_id, redacted=redacted) as uow:
            try:
                yield uow
            except Exception as e:
                logger.error(f"Error in unit of work: {e}")
                raise e
            else:
                if self.event_publisher is not None and uow.committed:
                    for event in uow.collect_events():
                        await self.event_publisher(event)

    @abstractmethod
    def _get_uow(
            self,
            user_id: int|None = None,
            redacted: bool = True
    ) -> AbstractAsyncContextManager[AbstractUnitHolder]:
        ...

