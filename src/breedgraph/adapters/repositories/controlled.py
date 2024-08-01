from abc import ABC, abstractmethod

from pydantic import BaseModel
from neo4j import AsyncTransaction

from src.breedgraph.custom_exceptions import UnauthorisedOperationError

from src.breedgraph.adapters.repositories.trackable_wrappers import Tracked, TrackedList
from src.breedgraph.adapters.repositories.base import BaseRepository

from src.breedgraph.domain.model.accounts import AccountStored
from src.breedgraph.domain.model.organisations import Organisation
from src.breedgraph.domain.model.controls import (
    Control,
    WriteStamp,
    Controller,
    ControlledModel,
    ControlledAggregate
)

from src.breedgraph.adapters.neo4j.cypher import controls


from typing import List, Tuple, AsyncGenerator, Set, ClassVar

import logging

logger = logging.getLogger(__name__)

class ControlledRepository(BaseRepository, ABC):

    def __init__(
            self,
            user_id: int = None,
            read_teams: List[int] = None,
            write_teams: List[int] = None,
            admin_teams: List[int] = None,
            curate_teams: List[int] = None
    ):
        super().__init__()
        self.user_id = user_id
        self.read_teams = read_teams if read_teams is not None else []
        self.write_teams = write_teams if write_teams is not None else []
        self.admin_teams = admin_teams if admin_teams is not None else []
        self.curate_teams = curate_teams if curate_teams is not None else []

    async def _create(
            self,
            aggregate_input: BaseModel
    ) -> ControlledAggregate:
        if self.user_id is None:
            raise ValueError("Only registered users may create controlled records")

        aggregate = await self._create_controlled(aggregate_input)
        return aggregate.redacted(self.read_teams)

    @abstractmethod
    async def _create_controlled(self, aggregate_input: BaseModel) -> ControlledAggregate:
        raise NotImplementedError

    async def _get(self, **kwargs) -> ControlledAggregate:
        aggregate = await self._get_controlled(**kwargs)
        if aggregate is not None:
            return aggregate.redacted(self.read_teams)

    @abstractmethod
    async def _get_controlled(self, **kwargs) -> ControlledAggregate:
        raise NotImplementedError

    async def _get_all(self, **kwargs) -> AsyncGenerator[ControlledAggregate, None]:
        async for aggregate in self._get_all_controlled():
            redacted = aggregate.redacted(self.read_teams)
            if redacted is not None:
                yield redacted

    @abstractmethod
    def _get_all_controlled(self) -> AsyncGenerator[ControlledAggregate, None]:
        raise NotImplementedError

    async def _remove(self, aggregate: ControlledAggregate):
        await self._remove_controlled(aggregate)

    @abstractmethod
    async def _remove_controlled(self, aggregate: ControlledAggregate):
        # ensure admin access to relevant records that make up the aggregate
        raise NotImplementedError

    async def _update(self, aggregate: ControlledAggregate|Tracked):
        if not aggregate.changed:
            return

        if self.user_id is None:
            raise ValueError("Only registered accounts may create controlled records")

        await self._update_controlled(aggregate)

    @abstractmethod
    async def _update_controlled(self, aggregate: ControlledAggregate|Tracked):
        # ensure curate access to relevant records that make up the aggregate
        raise NotImplementedError

    async def _update_entity_controller(self, entity: Tracked | ControlledModel):
        controller = entity.controller
        if controller.changed:
            for i in controller.controls.changed:
                control = controller.controls[i]
                await self._update_control(entity, control)
            for i in controller.controls.added:
                control = controller.controls[i]
                await self._create_control(entity, control)
            for i in controller.controls.removed:
                control = controller.controls[i]
                await self._remove_control(entity, control)

    @abstractmethod
    async def _update_control(self, entity: ControlledModel, control: Control):
        raise NotImplementedError

    @abstractmethod
    async def _create_control(self, entity: ControlledModel, control: Control):
        raise NotImplementedError

    @abstractmethod
    async def _remove_control(self, entity: ControlledModel, control: Control):
        raise NotImplementedError

class Neo4jControlledRepository(ControlledRepository, ABC):

    def __init__(self, tx: AsyncTransaction, **kwargs):
        super().__init__(**kwargs)
        self.tx = tx

    async def _update_control(self, entity: ControlledModel, control: Control):
        await self.tx.run(
            controls.set_control(label=entity.label, plural=entity.plural),
            team_id=control.team,
            release=control.release,
            entity_id=entity.id
        )

    async def _create_control(self, entity: ControlledModel, control: Control):
        await self.tx.run(
            controls.create_control(label=entity.label, plural=entity.plural),
            team_id=control.team,
            release=control.release,
            entity_id=entity.id
        )

    async def _remove_control(self, entity: ControlledModel, control: Control):
        await self.tx.run(
            controls.remove_control(label=entity.label, plural=entity.plural),
            team_id=control.team,
            entity_id=entity.id
        )