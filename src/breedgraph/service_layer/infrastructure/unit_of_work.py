from abc import ABC, abstractmethod
from contextlib import asynccontextmanager, AbstractAsyncContextManager

from src.breedgraph.domain.events import Event
from src.breedgraph.domain.model.controls import ReadRelease
from src.breedgraph.service_layer.repositories import AbstractRepoHolder
from src.breedgraph.service_layer.application.access_control import AbstractAccessControlService
from src.breedgraph.service_layer.application import OntologyApplicationService, GermplasmApplicationService
from src.breedgraph.service_layer.infrastructure.constraints import AbstractConstraintsHandler
from src.breedgraph.service_layer.infrastructure.driver import AbstractAsyncDriver

from typing import List, AsyncGenerator

import logging
logger = logging.getLogger(__name__)


class AbstractUnitHolder(ABC):
    constraints: AbstractConstraintsHandler
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

class AbstractUnitOfWorkFactory(ABC):
    events: List[Event] = list()

    def __init__(self, driver: AbstractAsyncDriver):
        super().__init__()
        self.driver = driver

    @asynccontextmanager
    async def get_uow(self, user_id: int = None, redacted: bool = True):
        async with self._get_uow(user_id=user_id, redacted=redacted) as uow:
            try:
                yield uow
            except Exception as e:
                logger.error(f"Error in unit of work: {e}")
                raise e
            finally:
                logger.debug("Collect events from uow")
                self.events.extend(uow.repositories.collect_events())
                self.events.extend(uow.controls.collect_events())
                self.events.extend(uow.ontology.collect_events())
                self.events.extend(uow.germplasm.collect_events())

    @abstractmethod
    def _get_uow(self, user_id: int = None, redacted: bool = True) -> AbstractAsyncContextManager[AbstractUnitHolder, None]:
        ...

    def collect_events(self):
        while self.events:
            yield self.events.pop(0)


