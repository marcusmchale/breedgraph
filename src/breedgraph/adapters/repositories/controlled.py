from abc import ABC, abstractmethod

from pydantic import BaseModel
from neo4j import AsyncTransaction

from src.breedgraph.custom_exceptions import UnauthorisedOperationError

from src.breedgraph.adapters.repositories.trackable_wrappers import (
    Tracked,
    TrackedList,
    TrackedSet,
    TrackedDict,
    TrackedGraph
)

from src.breedgraph.adapters.repositories.base import BaseRepository

from src.breedgraph.domain.model.controls import (
    Access,
    Control,
    WriteStamp,
    ReadRelease,
    Controller,
    ControlledModel,
    ControlledAggregate
)
from src.breedgraph.domain.model.base import LabeledModel
from src.breedgraph.adapters.neo4j.cypher import controls


from typing import List, Tuple, AsyncGenerator, Set, ClassVar

import logging

logger = logging.getLogger(__name__)

class ControlledRepository(BaseRepository):

    def __init__(
            self,
            user_id: int = None,
            redacted: bool = True,
            read_teams: Set[int] = None,
            write_teams: Set[int] = None,
            admin_teams: Set[int] = None,
            curate_teams: Set[int] = None,
            release: ReadRelease = ReadRelease.PRIVATE
    ):
        """
        :param user_id: A registered user to record writes to models. Also required to view redacted forms of some models,
            e.g. Without user_id the People repository will return None rather than redacted for Person with ReadRelease.PRIVATE.
        :param read_teams: Teams for which read access to un-redacted forms of a model should be allowed
        :param write_teams: The teams to which control should be given for any new models created
        :param admin_teams: The teams to which admin access should be allowed. Only admins can modify controls.
        :param curate_teams: The teams to which curate access should be allowed. Only curators can modify existing models.
        :param release: The default read release for any controls created
        """
        super().__init__()
        self.user_id = user_id
        self.redacted = redacted
        self.read_teams = read_teams if read_teams is not None else set()
        self.write_teams = write_teams if write_teams is not None else set()
        self.admin_teams = admin_teams if admin_teams is not None else set()
        self.curate_teams = curate_teams if curate_teams is not None else set()
        self.release = release

    @property
    def control_parameters(self) -> dict:
        return {
            'writer': self.user_id,
            'controls': [{'team': team, 'release': self.release} for team in self.write_teams]
        }

    @staticmethod
    def get_controlled_models(aggregate: ControlledAggregate) -> List[ControlledModel]:
        # We can't return the wrapper (proxy) from the wrapped object (inside the proxy)
        # As sometimes our aggregate is itself a controlled model,
        # we want the wrapper around this root object itself to know about changes to the root object
        if isinstance(aggregate, ControlledModel) and isinstance(aggregate, ControlledAggregate):
            return [aggregate] + aggregate.controlled_models
        else:
            return aggregate.controlled_models

    async def _create(
            self,
            aggregate_input: BaseModel
    ) -> ControlledAggregate:
        if self.user_id is None:
            raise ValueError("User id is required in controlled repository to create models")
        if not self.write_teams:
            raise ValueError("Write teams is required in controlled repository to create models")

        aggregate = await self._create_controlled(aggregate_input)
        await self._create_controllers(aggregate)
        if self.redacted:
            return aggregate.redacted(user_id=self.user_id, read_teams=self.read_teams)
        else:
            return aggregate

    @abstractmethod
    async def _create_controlled(
            self, aggregate_input: BaseModel
    ) -> ControlledAggregate:
        raise NotImplementedError

    async def _create_controllers(self, aggregate: ControlledAggregate):
        for model in self.get_controlled_models(aggregate):
            await self._create_controller(model)

    @staticmethod
    def get_model_class( model: Tracked|BaseModel):
        if isinstance(model, Tracked):
            return type(model.__wrapped__)
        else:
            return type(model)

    async def _create_controller(self, model: ControlledModel):
        model_class = self.get_model_class(model)
        await self._record_write(entity_class=model_class, entity_id=model.id, user_id=self.user_id)
        for team_id in self.write_teams:
            await self._create_control(
                entity_class=model_class,
                entity_id=model.id,
                team_id=team_id,
                release=self.release
            )
        model.controller = await self._get_controller(model_class, model.id)

    async def _insert_controllers(self, aggregate: ControlledAggregate):
        for model in self.get_controlled_models(aggregate):
            model_class = self.get_model_class(model)
            model.controller = await self._get_controller(model_class, model.id)


    async def _get(self, **kwargs) -> ControlledAggregate:
        aggregate = await self._get_controlled(**kwargs)
        if aggregate is not None:
            await self._insert_controllers(aggregate)
            if self.redacted:
                return aggregate.redacted(user_id=self.user_id, read_teams=self.read_teams)
            else:
                return aggregate

    @abstractmethod
    async def _get_controlled(self, **kwargs) -> ControlledAggregate:
        raise NotImplementedError

    async def _get_all(self, **kwargs) -> AsyncGenerator[ControlledAggregate, None]:
        async for aggregate in self._get_all_controlled(**kwargs):
            await self._insert_controllers(aggregate)
            if self.redacted:
                redacted = aggregate.redacted(user_id=self.user_id, read_teams=self.read_teams)
                if redacted is not None:
                    yield redacted
            else:
                yield aggregate

    @abstractmethod
    def _get_all_controlled(self, **kwargs) -> AsyncGenerator[ControlledAggregate, None]:
        raise NotImplementedError

    async def _remove(self, aggregate: ControlledAggregate):
        if aggregate.protected:
            raise UnauthorisedOperationError(aggregate.protected)

        if aggregate.root.controller.has_access(Access.ADMIN, access_teams=self.admin_teams):
            raise UnauthorisedOperationError(f"Removal requires admin permission on the root {aggregate.root.label}")

        if not aggregate.root.controller.has_access(Access.CURATE, access_teams=self.curate_teams):
            raise UnauthorisedOperationError(f"Removal requires curate permission on the root {aggregate.root.label}")

        await self._remove_controlled(aggregate)

    @abstractmethod
    async def _remove_controlled(self, aggregate: ControlledAggregate):
        raise NotImplementedError

    async def _update(self, aggregate: ControlledAggregate|Tracked):
        if not aggregate.changed:
            return

        if self.user_id is None:
            raise UnauthorisedOperationError("Only registered accounts may update controlled records")

        if not self.write_teams and (aggregate.added_models or aggregate.changed_models):
            raise UnauthorisedOperationError("Write affiliation is required to add to or change controlled records")

        for model in aggregate.removed_models:
            if not model.controller.has_access(Access.CURATE, access_teams=self.curate_teams):
                raise UnauthorisedOperationError("Curate affiliation is required to remove controlled records")

        for model in aggregate.changed_models:
            if 'controller' in model.changed:
                if not model.controller.has_access(Access.ADMIN, access_teams=self.admin_teams):
                    raise UnauthorisedOperationError(
                        f"Changes to {model.label} controller changes requires admin affiliation to a control team for the corresponding record"
                    )

            if model.changed and model.changed != {'controller'}:
                if not model.controller.has_access(Access.CURATE, access_teams=self.curate_teams):
                    for attr in model.changed:
                        value = getattr(model, attr)
                        if isinstance(value, (TrackedList, TrackedSet, TrackedDict)):
                            if value.added:
                                raise UnauthorisedOperationError(
                                    "Curate affiliation is required to add to collections in controlled models"
                                )
                            if value.removed:
                                raise UnauthorisedOperationError(
                                    "Curate affiliation is required to remove from collections in controlled models"
                                )
                        elif isinstance(value, TrackedGraph):
                            if value.added_nodes or value.added_edges:
                                raise UnauthorisedOperationError(
                                    "Curate affiliation is required to add nodes or edges to controlled graph models"
                                )
                            if value.removed_nodes or value.removed_edges:
                                raise UnauthorisedOperationError(
                                    "Curate affiliation is required to remove nodes or edges from controlled graph models"
                                )
                        else:
                            raise UnauthorisedOperationError("Curate affiliation is required to change controlled records")

        await self._update_controlled(aggregate)

        for model in aggregate.added_models:
            if not isinstance(model, ControlledModel):
                model_class = self.get_model_class(aggregate.root)
                await self._record_write(entity_class=model_class, entity_id=aggregate.root.id, user_id=self.user_id)

            else:
                await self._create_controller(model)
                model_class = self.get_model_class(model)
                await self._record_write(entity_class=model_class, entity_id=model.id, user_id=self.user_id)

        for model in aggregate.changed_models:
            if 'controller' in model.changed and not model in aggregate.added_models:
                await self._update_entity_controller(model)
                model.changed.remove('controller')
            if model.changed:  # we don't record writes when only the controller has changed
                model_class = self.get_model_class(model)
                await self._record_write(entity_class=model_class, entity_id=model.id, user_id=self.user_id)

    @abstractmethod
    async def _update_controlled(self, aggregate: ControlledAggregate|Tracked):
        raise NotImplementedError

    async def _update_entity_controller(self, entity: Tracked | ControlledModel):
        if not hasattr(entity, 'id'):
            raise ValueError("Only stored entities can be updated, these should have an id attribute")

        controller = entity.controller
        model_class = self.get_model_class(entity)
        if controller.changed:
            for i in controller.controls.added:
                await self._create_control(
                    entity_class=model_class,
                    entity_id = entity.id,
                    team_id = i,
                    release = controller.controls[i].release
                )
            for team_id in controller.controls.changed:
                control = controller.controls[team_id]
                await self._update_control(entity, team_id, control.release)

            for team_id in controller.controls.removed:
                await self._remove_control(entity, team_id)

    @abstractmethod
    async def _record_write(self, entity_class: type[LabeledModel], entity_id: int, user_id: int):
        raise NotImplementedError

    @abstractmethod
    async def _create_control(self, entity_class: type[LabeledModel], entity_id: int, team_id: int, release: ReadRelease):
        raise NotImplementedError

    @abstractmethod
    async def _get_controller(self,entity_class: type[LabeledModel], entity_id: int):
        raise NotImplementedError

    @abstractmethod
    async def _update_control(self, entity: ControlledModel, team_id: int, control: Control):
        raise NotImplementedError

    @abstractmethod
    async def _remove_control(self, entity: ControlledModel, team_id: int):
        raise NotImplementedError


class Neo4jControlledRepository(ControlledRepository):

    def __init__(self, tx: AsyncTransaction, **kwargs):
        super().__init__(**kwargs)
        self.tx = tx

    async def _record_write(self, entity_class: type[LabeledModel], entity_id: int, user_id: int):
        result = await self.tx.run(
            controls.record_write(label=entity_class.label, plural=entity_class.plural),
            entity_id=entity_id,
            user_id=user_id
        )
        record = await result.single()
        return WriteStamp(**record)

    async def _create_control(self, entity_class: type[LabeledModel], entity_id: int, team_id: int, release: ReadRelease):
        result = await self.tx.run(
            controls.create_control(label=entity_class.label, plural=entity_class.plural),
            entity_id=entity_id,
            team_id=team_id,
            release=release
        )
        control_record = await result.single()
        return Control(**control_record['control'])

    async def _update_control(self, entity: ControlledModel, team_id: int,  release: ReadRelease):
        await self.tx.run(
            controls.set_control(label=entity.label, plural=entity.plural),
            entity_id=entity.id,
            team_id=team_id,
            release=release
        )

    async def _remove_control(self, entity: ControlledModel, team_id: int):
        await self.tx.run(
            controls.remove_control(label=entity.label, plural=entity.plural),
            entity_id=entity.id,
            team_id=team_id
        )

    async def _get_controller(self, entity_class: type[LabeledModel], entity_id: int):
        result = await self.tx.run(
            controls.get_controller(label=entity_class.label, plural=entity_class.plural),
            entity_id=entity_id
        )
        record = await result.single()
        control_map = {
            control['team']: {'release': control['release'],'time': control['time']}
            for control in record['controls']
        }
        writes = record.get('writes')
        return Controller(controls=control_map, writes=writes)

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