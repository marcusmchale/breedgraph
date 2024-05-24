from abc import ABC, abstractmethod
from typing import Set, List, AsyncGenerator

from pydantic import BaseModel, Field

from src.breedgraph.adapters.repositories.trackable_wrappers import Tracked
from src.breedgraph.custom_exceptions import ProtectedNodeError

from src.breedgraph.domain.model.base import Entity, Aggregate

from typing import Union


class BaseRepository(ABC):

    def __init__(self):
        self.seen: Set[Tracked|Aggregate] = set()

    def _track(self, aggregate: Aggregate) -> Tracked|Aggregate:
        tracked = Tracked(aggregate)
        self.seen.add(tracked)
        return tracked

    async def create(self, aggregate_input: BaseModel) -> Tracked|Aggregate:
        aggregate = await self._create(aggregate_input)
        tracked_aggregate = self._track(aggregate)
        return tracked_aggregate

    @abstractmethod
    async def _create(self, aggregate_input: BaseModel) -> Aggregate:
        raise NotImplementedError

    async def get(self, **kwargs) -> Tracked|Aggregate:
        aggregate = await self._get(**kwargs)
        if aggregate is not None:
            return self._track(aggregate)

    @abstractmethod
    async def _get(self, **kwargs) -> Aggregate:  # get may be from root id or ID of list_attribute elements
        raise NotImplementedError

    async def get_all(self, **kwargs) -> AsyncGenerator[Tracked|Aggregate, None]:
        async for aggregate in self._get_all(**kwargs):
            yield self._track(aggregate)

    @abstractmethod
    def _get_all(self, **kwargs) -> AsyncGenerator[Aggregate, None]:
        # each attr is stored with a list of values to filter by
        raise NotImplementedError

    async def remove(self, aggregate: Tracked|Aggregate) -> None:
        if aggregate.protected:
            raise ProtectedNodeError(aggregate.protected)

        await self._remove(aggregate)
        self.seen.remove(aggregate)

    @abstractmethod
    async def _remove(self, aggregate: Tracked|Aggregate) -> None:
        raise NotImplementedError

    async def update_seen(self):
        for aggregate in self.seen:
            await self._update(aggregate)
            aggregate.reset_tracking()

    @abstractmethod
    async def _update(self, aggregate: Tracked|Aggregate):
        raise NotImplementedError
