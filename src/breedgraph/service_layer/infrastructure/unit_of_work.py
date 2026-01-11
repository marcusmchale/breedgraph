from abc import ABC, abstractmethod
from contextlib import asynccontextmanager

from src.breedgraph.domain.events import Event
from src.breedgraph.domain.model.controls import ReadRelease
from src.breedgraph.service_layer.repositories import AbstractRepoHolder
from src.breedgraph.service_layer.application.access_control import AbstractAccessControlService
from src.breedgraph.service_layer.application import OntologyApplicationService, GermplasmApplicationService
from src.breedgraph.service_layer.queries.views import AbstractViewsHolder

from typing import List

import logging
logger = logging.getLogger(__name__)


class AbstractUnitHolder(ABC):
    views: AbstractViewsHolder
    controls: AbstractAccessControlService
    ontology: OntologyApplicationService
    germplasm: GermplasmApplicationService
    repositories: AbstractRepoHolder

    @abstractmethod
    async def commit(self):
        raise NotImplementedError

    @abstractmethod
    async def rollback(self):
        raise NotImplementedError

    @abstractmethod
    async def db_is_empty(self) -> bool:
        raise NotImplementedError

class AbstractUnitOfWork(ABC):
    events: List[Event] = list()

    @asynccontextmanager
    async def get_uow(self, user_id: int = None, redacted: bool = True, release: ReadRelease = ReadRelease.PRIVATE):
        async with self._get_uow(user_id=user_id, redacted=redacted, release=release) as uow:
            try:
                yield uow
            finally:
                logger.debug("Collect events from uow")
                self.events.extend(uow.repositories.collect_events())
                self.events.extend(uow.controls.collect_events())
                self.events.extend(uow.ontology.collect_events())
                self.events.extend(uow.germplasm.collect_events())

    @abstractmethod
    @asynccontextmanager
    async def _get_uow(self, user_id: int = None, redacted: bool = True) -> AbstractUnitHolder:
        raise NotImplementedError

    def collect_events(self):
        while self.events:
            yield self.events.pop(0)


