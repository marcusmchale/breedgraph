from abc import ABC, abstractmethod
from typing import Dict, AsyncGenerator, TypeVar, Generic, Union, List, cast
from neo4j import Record

from breedgraph.service_layer.tracking import TrackableProtocol, TrackedObject, tracked
from breedgraph.domain.model.time_descriptors import deserialize_time, serialize_npdt64
from breedgraph.custom_exceptions import ProtectedNodeError
from breedgraph.domain.model.base import Aggregate

TAggregateInput = TypeVar("TAggregateInput")
TAggregate = TypeVar("TAggregate", bound=Aggregate)

class BaseRepository(ABC, Generic[TAggregateInput, TAggregate]):

    def __init__(self):
        self.seen: Dict[TrackedObject|TAggregate,TrackedObject|TAggregate] = dict()
        # Kept so their events are still published once the removal is committed
        self.removed: List[TrackedObject|TAggregate] = list()

    @staticmethod
    def deserialize_dt64(record: Dict | Record) -> dict:
        if isinstance(record, Record):
            record = record.data()

        if record.get('submitted', None) is not None:
            record['submitted'] = deserialize_time(record['submitted'])
        for key in ('start', 'end', 'time'):
            # a time's unit and step are read with it, and left out with it
            unit, step = record.pop(f'{key}_unit', None), record.pop(f'{key}_step', None)
            if record.get(key, None) is not None:
                record[key] = deserialize_time(record[key], unit, step)
        return record

    @staticmethod
    def serialize_dt64(record: dict, to_neo4j: bool = False) -> dict:
        if record.get('submitted', None) is not None:
            record.pop('submitted')  # we don't want to update submitted timestamp, this is set by neo4j tx
        for key in ('start', 'end', 'time'):
            if record.get(key, None) is not None:
                serialized = serialize_npdt64(record[key], to_neo4j=to_neo4j)
                record.update({
                    key: serialized['time'],
                    f'{key}_unit': serialized['unit'],
                    f'{key}_step': serialized['step']
                })
            elif key in record:
                # a time cleared takes its unit and step with it, as `SET node += $data` removes what is null
                record.update({f'{key}_unit': None, f'{key}_step': None})
        return record

    def _track(self, aggregate: TAggregate) -> Union[TrackedObject|TAggregate]:
        # Check if this aggregate is already being tracked,
        # if so return the tracked version rather than the refetched version
        if aggregate in self.seen:
            return cast(TAggregate, self.seen[aggregate])

        tracked_aggregate = tracked(aggregate)
        self.seen[tracked_aggregate]=tracked_aggregate
        return cast(TAggregate, tracked_aggregate)

    async def create(self, aggregate_input: TAggregateInput) -> TAggregate:
        aggregate = await self._create(aggregate_input)
        tracked_aggregate = self._track(aggregate)
        return cast(TAggregate, tracked_aggregate)

    @abstractmethod
    async def _create(self, aggregate_input: TAggregateInput) -> TAggregate:
        ...

    async def get(self, **kwargs) -> TAggregate|None:
        aggregate = await self._get(**kwargs)
        if aggregate is not None:
            return cast(TAggregate, self._track(aggregate))
        return None

    @abstractmethod
    async def _get(self, **kwargs) -> Aggregate | None:  # get may be from root id or ID of list_attribute elements
        ...

    async def get_all(self, **kwargs) -> AsyncGenerator[Union[TrackedObject, TAggregate], None]:
        async for aggregate in self._get_all(**kwargs):
            yield self._track(aggregate)

    @abstractmethod
    def _get_all(self, **kwargs) -> AsyncGenerator[TAggregate, None]:
        # each attr is stored with a list of values to filter by
        ...

    async def remove(self, aggregate: Union[TrackedObject, TAggregate]) -> None:
        if aggregate.protected:
            raise ProtectedNodeError(aggregate.protected)

        await self._remove(aggregate)
        self.seen.pop(aggregate)
        self.removed.append(aggregate)

    @abstractmethod
    async def _remove(self, aggregate: Union[TrackedObject, TAggregate]) -> None:
        ...

    async def update_seen(self):
        for aggregate, tracked_aggregate in self.seen.items():
            await self._update(tracked_aggregate)
            tracked_aggregate.reset_tracking()

    @abstractmethod
    async def _update(self, aggregate: Union[TrackedObject, TAggregate]):
        ...
