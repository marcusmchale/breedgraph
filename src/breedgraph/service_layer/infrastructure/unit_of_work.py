from abc import ABC, abstractmethod
from contextlib import asynccontextmanager, AbstractAsyncContextManager

from breedgraph.domain.events import Event

from breedgraph.service_layer.repositories import AbstractRepoHolder

from breedgraph.service_layer.application import (
    OntologyApplicationService,
    GermplasmApplicationService,
    AbstractAggregateRestructuringService,
    AbstractAccessControlService
)

from .constraints import AbstractConstraintsHandler
from .dependency_guards import AbstractDependencyGuards
from .driver import AbstractAsyncDriver


from typing import AsyncGenerator, Callable, Awaitable, Iterable

import logging

from ...domain.model import ReadRelease

logger = logging.getLogger(__name__)

EventPublisher = Callable[[Event], Awaitable[None]]

class AbstractUnitHolder(ABC):

    constraints: AbstractConstraintsHandler
    controls: AbstractAccessControlService
    ontology: OntologyApplicationService
    germplasm: GermplasmApplicationService
    repositories: AbstractRepoHolder
    restructuring: AbstractAggregateRestructuringService
    guards: AbstractDependencyGuards
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
        self.publish_event: EventPublisher | None = None

    def set_event_publisher(self, event_publisher: EventPublisher|None):
        self.publish_event = event_publisher

    @asynccontextmanager
    async def get_uow(
            self,
            user_id: int|None = None,
            redacted: bool = True,
            write_team: int | None = None,
            release: ReadRelease = ReadRelease.PRIVATE
    ) -> AsyncGenerator[AbstractUnitHolder, None]:
        async with self._get_uow(user_id=user_id, redacted=redacted, write_team=write_team, release=release) as uow:
            try:
                yield uow
            except Exception as e:
                logger.exception(f"Error in unit of work: {e}")
                raise e
            else:
                if self.publish_event is not None and uow.committed:
                    for event in uow.collect_events():
                        await self.publish_event(event)

    @abstractmethod
    def _get_uow(
            self,
            user_id: int|None = None,
            redacted: bool = True,
            write_team: int | None = None,
            release: ReadRelease = ReadRelease.PRIVATE
    ) -> AbstractAsyncContextManager[AbstractUnitHolder]:
        ...

