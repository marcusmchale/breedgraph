from abc import ABC, abstractmethod
from typing import Dict, AsyncGenerator, TypeVar, Generic, Union

from src.breedgraph.service_layer.tracking import TrackableProtocol, TrackedObject, tracked
from src.breedgraph.domain.model.time_descriptors import deserialize_time, serialize_npdt64, npdt64_to_neo4j
from src.breedgraph.custom_exceptions import ProtectedNodeError
from src.breedgraph.domain.model.base import Aggregate

TAggregateInput = TypeVar("TAggregateInput")
TAggregate = TypeVar("TAggregate", bound=Aggregate)

class BaseRepository(ABC, Generic[TAggregateInput, TAggregate]):

    def __init__(self):
        self.seen: Dict[TrackedObject|TAggregate,TrackedObject|TAggregate] = dict()

    @staticmethod
    def deserialize_dt64(record: dict) -> dict:
        if record.get('submitted', None) is not None:
            record['submitted'] = deserialize_time(record['submitted'])
        if record.get('start', None) is not None:
            record['start'] = deserialize_time(record['start'], record.pop('start_unit'), record.pop('start_step'))
        if record.get('end', None) is not None:
            record['end'] = deserialize_time(record['end'], record.pop('end_unit'), record.pop('end_step'))
        if record.get('time', None) is not None:
            record['time'] = deserialize_time(record['time'], record.pop('time_unit'), record.pop('time_step'))
        return record

    @staticmethod
    def serialize_dt64(record: dict, to_neo4j: bool = False) -> dict:
        if record.get('submitted', None) is not None:
            record.pop('submitted')  # we don't want to update submitted timestamp, this is set by neo4j tx
        if record.get('start', None) is not None:
            serialized = serialize_npdt64(record['start'], to_neo4j=to_neo4j)
            record.update({
                'start': serialized['time'],
                'start_unit': serialized['unit'],
                'start_step': serialized['step']
            })
        if record.get('end', None) is not None:
            serialized = serialize_npdt64(record['end'], to_neo4j=to_neo4j)
            record.update({
                'end': serialized['time'],
                'end_unit': serialized['unit'],
                'end_step': serialized['step']
            })
        if record.get('time', None) is not None:
            serialized = serialize_npdt64(record['time'], to_neo4j=to_neo4j)
            record.update({
                'time': serialized['time'],
                'time_unit': serialized['unit'],
                'time_step': serialized['step']
            })
        return record

    def _track(self, aggregate: TAggregate) -> Union[TrackedObject|TAggregate]:
        # Check if this aggregate is already being tracked,
        # if so return the tracked version rather than the refetched version
        if aggregate in self.seen:
            return self.seen[aggregate]

        tracked_aggregate = tracked(aggregate)
        self.seen[tracked_aggregate]=tracked_aggregate
        return tracked_aggregate

    async def create(self, aggregate_input: TAggregateInput|None = None) -> Union[TrackedObject, TAggregate]:
        aggregate = await self._create(aggregate_input)
        tracked_aggregate = self._track(aggregate)
        return tracked_aggregate

    @abstractmethod
    async def _create(self, aggregate_input: TAggregateInput|None) -> TAggregate:
        ...

    async def get(self, **kwargs) -> Union[TrackedObject, TAggregate, None]:
        aggregate = await self._get(**kwargs)
        if aggregate is not None:
            return self._track(aggregate)
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
