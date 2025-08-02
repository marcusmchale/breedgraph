from abc import ABC, abstractmethod

from pydantic import BaseModel
from neo4j import AsyncTransaction
from numpy import datetime64

from src.breedgraph.custom_exceptions import UnauthorisedOperationError

from src.breedgraph.adapters.repositories.trackable_wrappers import Tracked

from src.breedgraph.adapters.repositories.base import BaseRepository
from src.breedgraph.service_layer.controllers_service import AbstractControllersService
from src.breedgraph.domain.model.controls import (
    Access,
    ControlledModel,
    ControlledAggregate, ReadRelease
)


from typing import Dict, List, Tuple, AsyncGenerator, Set, ClassVar

import logging

logger = logging.getLogger(__name__)

class ControlledRepository(BaseRepository):

    def __init__(
            self,
            controllers_service: AbstractControllersService,
            user_id: int = None,
            access_teams: Dict[Access, Set[int]] = None,
            release: ReadRelease = ReadRelease.PRIVATE,
    ):
        super().__init__()
        self.controllers_service = controllers_service
        self.user_id = user_id
        if access_teams is None:
            access_teams = {}
        self.access_teams = {access: access_teams.get(access, set()) for access in Access}
        self.release = release

    async def _create(
            self,
            aggregate_input: BaseModel
    ) -> ControlledAggregate:
        aggregate = await self._create_controlled(aggregate_input)
        await self.controllers_service.set_controls(
            aggregate,
            control_teams=self.access_teams[Access.WRITE],
            release=self.release
        )
        controllers = await self.controllers_service.get_controllers_for_aggregate(aggregate)
        await self.controllers_service.record_writes(aggregate, user_id=self.user_id)
        return aggregate.redacted(
            controllers=controllers,
            user_id=self.user_id,
            read_teams=self.access_teams[Access.READ]
        )

    @abstractmethod
    async def _create_controlled(
            self, aggregate_input: BaseModel
    ) -> ControlledAggregate:
        raise NotImplementedError

    async def _get(self, **kwargs) -> ControlledAggregate | None:
        aggregate = await self._get_controlled(**kwargs)
        if aggregate is not None:
            controllers = await self.controllers_service.get_controllers_for_aggregate(aggregate)
            return aggregate.redacted(
                controllers=controllers,
                user_id=self.user_id,
                read_teams=self.access_teams[Access.READ]
            )
        return None

    @abstractmethod
    async def _get_controlled(self, **kwargs) -> ControlledAggregate:
        raise NotImplementedError

    async def _get_all(self, **kwargs) -> AsyncGenerator[ControlledAggregate, None]:
        async for aggregate in self._get_all_controlled(**kwargs):
            if aggregate is not None:
                controllers = await self.controllers_service.get_controllers_for_aggregate(aggregate)
                aggregate = aggregate.redacted(
                    controllers=controllers,
                    user_id=self.user_id,
                    read_teams=self.access_teams[Access.READ]
                )
                if aggregate is not None:
                    yield aggregate

    @abstractmethod
    def _get_all_controlled(self, **kwargs) -> AsyncGenerator[ControlledAggregate, None]:
        raise NotImplementedError

    async def _remove(self, aggregate: ControlledAggregate):
        if aggregate.protected:
            raise UnauthorisedOperationError(aggregate.protected)
        controllers = await self.controllers_service.get_controllers_for_aggregate(aggregate)
        if not aggregate.can_remove(controllers, self.user_id, self.access_teams[Access.CURATE]):
            raise UnauthorisedOperationError(
                f"Removal requires curate permission for all teams that control entities in this {aggregate.root.label}"
            )
        await self._remove_controlled(aggregate)

    @abstractmethod
    async def _remove_controlled(self, aggregate: ControlledAggregate):
        raise NotImplementedError

    async def _update(self, aggregate: ControlledAggregate|Tracked):
        if not aggregate.changed:
            return

        controllers = await self.controllers_service.get_controllers_for_aggregate(aggregate)
        for model in aggregate.removed_models:
            if isinstance(model, ControlledModel):
                controller = controllers[model.label][model.id]
                if not controller.has_access(Access.CURATE, access_teams=self.access_teams[Access.CURATE]):
                    raise UnauthorisedOperationError(f"Curate affiliation is required to remove {model.label} (id: {model.id})")

        for model in aggregate.changed_models:
            if isinstance(model, ControlledModel):
                controller = controllers[model.label][model.id]
                if not controller.has_access(Access.CURATE, access_teams=self.access_teams[Access.CURATE]):
                    raise UnauthorisedOperationError(
                        f"Curate affiliation is required to change {model.label} (id: {model.id})")

        await self._update_controlled(aggregate)

        controlled_added = [i for i in aggregate.added_models if isinstance(i, ControlledModel)]
        await self.controllers_service.set_controls(
            controlled_added,
            control_teams=self.access_teams[Access.WRITE],
            release=self.release
        )
        controlled_updates = [i for i in aggregate.changed_models if isinstance(i, ControlledModel)]
        await self.controllers_service.record_writes(
            controlled_updates + controlled_added,
            user_id=self.user_id
        )

    @abstractmethod
    async def _update_controlled(self, aggregate: ControlledAggregate|Tracked):
        raise NotImplementedError


class Neo4jControlledRepository(ControlledRepository):

    def __init__(self, tx: AsyncTransaction, **kwargs):
        super().__init__(**kwargs)
        self.tx = tx

    @staticmethod
    def times_to_dt64(record):
        if 'start' in record:
            record['start'] = datetime64(record['start'], (record['start_unit'], record['start_step']))
        if 'end' in record:
            record['end'] = datetime64(record['end'], (record['end_unit'], record['end_step']))
        if 'time' in record:
            record['time'] = datetime64(record['time'], (record['time_unit'], record['time_step']))

    @abstractmethod
    async def _create_controlled(self, aggregate_input: BaseModel) -> ControlledAggregate:
        raise NotImplementedError

    @abstractmethod
    async def _get_controlled(self, **kwargs) -> ControlledAggregate:
        raise NotImplementedError

    @abstractmethod
    def _get_all_controlled(self, **kwargs) -> AsyncGenerator[ControlledAggregate, None]:
        raise NotImplementedError

    @abstractmethod
    async def _remove_controlled(self, aggregate: ControlledAggregate):
        raise NotImplementedError

    @abstractmethod
    async def _update_controlled(self, aggregate: ControlledAggregate | Tracked):
        raise NotImplementedError