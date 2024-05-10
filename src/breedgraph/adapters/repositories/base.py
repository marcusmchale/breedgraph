from abc import ABC, abstractmethod
from typing import Set, List, AsyncGenerator

from pydantic import BaseModel

from src.breedgraph.adapters.repositories.trackable_wrappers import Tracked, TrackedList
from src.breedgraph.custom_exceptions import ProtectedNodeError

class Entity(BaseModel):
    id: int

class AggregateRoot(Entity):
    id: int

class Aggregate(BaseModel):

    @property
    @abstractmethod
    def root(self) -> AggregateRoot:
        raise NotImplementedError


    @property
    @abstractmethod
    def protected(self) -> str|bool: # Return an error message if protected or False if safe to remove
        raise NotImplementedError
        # e.g. for an account, if email is verified we no longer want to allow a removal.

class BaseRepository(ABC):

    def __init__(self):
        self.seen: Set[Aggregate] = set()

    def _track(self, aggregate: Aggregate) -> None:
        aggregate.root = Tracked(aggregate.root)
        for attr in aggregate.root.model_fields.keys():
            if isinstance(getattr(aggregate.root, attr), list):
                setattr(self, attr, TrackedList(getattr(self, attr)))
        self.seen.add(aggregate)

    async def create(self, aggregate: Aggregate) -> Aggregate:
        aggregate_stored = await self._create(aggregate)
        self._track(aggregate)
        return aggregate_stored

    @abstractmethod
    async def _create(self, aggregate: Aggregate) -> Aggregate:
        raise NotImplementedError

    async def get(self, db_id: int) -> Aggregate:
        aggregate = await self._get(db_id)
        if aggregate is not None:
            self._track(aggregate)
        return aggregate

    @abstractmethod
    async def _get(self, db_id: int) -> Aggregate:  # get may be from root id or ID of list_attribute elements
        raise NotImplementedError

    async def get_all(self) -> AsyncGenerator[Aggregate, None]:
        async for aggregate in self._get_all():
            self._track(aggregate)
            yield aggregate

    @abstractmethod
    def _get_all(self) -> AsyncGenerator[Aggregate, None]:
        raise NotImplementedError

    async def remove(self, aggregate: Aggregate) -> None:
        if aggregate.protected:
            raise ProtectedNodeError(aggregate.protected)

        await self._remove(aggregate)

    @abstractmethod
    async def _remove(self, aggregate: Aggregate) -> None:
        raise NotImplementedError

    async def update_seen(self):
        for aggregate in self.seen:
            await self._update(aggregate)
        self.seen.clear()

    @abstractmethod
    async def _update(self, aggregate: Aggregate):
        raise NotImplementedError
