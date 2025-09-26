from abc import abstractmethod
from typing import Dict, Set, AsyncGenerator, TypeVar, Generic

from pydantic import BaseModel

from src.breedgraph.service_layer.tracking import TrackableProtocol, TrackedObject
from src.breedgraph.service_layer.repositories.base import BaseRepository, TAggregateInput
from src.breedgraph.custom_exceptions import UnauthorisedOperationError
from src.breedgraph.domain.model.controls import ReadRelease, ControlledAggregate, ControlledModel
from src.breedgraph.domain.model.organisations import Access
from src.breedgraph.service_layer.application.access_control import AbstractAccessControlService

TControlledAggregate = TypeVar("TControlledAggregate", bound=ControlledAggregate)

class ControlledRepository(
    Generic[TAggregateInput, TControlledAggregate],
    BaseRepository[TAggregateInput, TControlledAggregate]
):

    def __init__(
            self,
            access_control_service: AbstractAccessControlService,
            release: ReadRelease = ReadRelease.PRIVATE,
    ):
        super().__init__()
        self.access_control_service = access_control_service
        self.release = release

    @property
    def user_id(self):
        return self.access_control_service.user_id

    @property
    def access_teams(self):
        return self.access_control_service.access_teams

    async def _create(
            self,
            aggregate_input: BaseModel
    ) -> TControlledAggregate:
        aggregate = await self._create_controlled(aggregate_input)
        await self.access_control_service.set_controls(
            aggregate,
            control_teams=self.access_teams[Access.WRITE],
            release=self.release,
            user_id=self.user_id
        )
        controllers = await self.access_control_service.get_controllers_for_aggregate(aggregate)
        await self.access_control_service.record_writes(aggregate, user_id=self.user_id)
        return aggregate.redacted(
            controllers=controllers,
            user_id=self.user_id,
            read_teams=self.access_teams[Access.READ]
        )

    @abstractmethod
    async def _create_controlled(
            self, aggregate_input: BaseModel
    ) -> TControlledAggregate:
        raise NotImplementedError

    async def _get(self, **kwargs) -> TControlledAggregate | None:
        aggregate = await self._get_controlled(**kwargs)
        if aggregate is not None:
            controllers = await self.access_control_service.get_controllers_for_aggregate(aggregate)
            return aggregate.redacted(
                controllers=controllers,
                user_id=self.user_id,
                read_teams=self.access_teams[Access.READ]
            )
        return None

    @abstractmethod
    async def _get_controlled(self, **kwargs) -> TControlledAggregate:
        raise NotImplementedError

    async def _get_all(self, **kwargs) -> AsyncGenerator[TControlledAggregate, None]:
        async for aggregate in self._get_all_controlled(**kwargs):
            if aggregate is not None:
                controllers = await self.access_control_service.get_controllers_for_aggregate(aggregate)
                aggregate = aggregate.redacted(
                    controllers=controllers,
                    user_id=self.user_id,
                    read_teams=self.access_teams[Access.READ]
                )
                if aggregate is not None:
                    yield aggregate

    @abstractmethod
    def _get_all_controlled(self, **kwargs) -> AsyncGenerator[TControlledAggregate, None]:
        raise NotImplementedError

    async def _remove(self, aggregate: TControlledAggregate):
        if aggregate.protected:
            raise UnauthorisedOperationError(aggregate.protected)
        controllers = await self.access_control_service.get_controllers_for_aggregate(aggregate)
        if not aggregate.can_remove(controllers, self.user_id, self.access_teams[Access.CURATE]):
            raise UnauthorisedOperationError(
                f"Removal requires curate permission for all teams that control entities in this {aggregate.root.label}"
            )
        await self._remove_controlled(aggregate)

    @abstractmethod
    async def _remove_controlled(self, aggregate: TControlledAggregate):
        raise NotImplementedError

    async def _update(self, aggregate: TControlledAggregate | TrackedObject):
        if not aggregate.changed:
            return

        controllers = await self.access_control_service.get_controllers_for_aggregate(aggregate)
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
        await self.access_control_service.set_controls(
            controlled_added,
            control_teams=self.access_teams[Access.WRITE],
            release=self.release,
            user_id=self.user_id
        )
        controlled_updates = [i for i in aggregate.changed_models if isinstance(i, ControlledModel)]
        await self.access_control_service.record_writes(
            controlled_updates + controlled_added,
            user_id=self.user_id
        )

    @abstractmethod
    async def _update_controlled(self, aggregate: TControlledAggregate | TrackedObject):
        raise NotImplementedError

    async def set_entity_access_controls(
            self,
            entity: ControlledModel,
            control_teams: Set[int],
            release: ReadRelease
    ) -> None:
        """Set access controls for a specific entity within the aggregate"""
        # Get the current controller for this specific entity
        controller = await self.access_control_service.get_controller(
            entity.label,
            entity.id
        )

        # Check authorization for this specific entity
        if not controller.has_access(Access.ADMIN, access_teams=self.access_teams[Access.ADMIN]):
            raise UnauthorisedOperationError(
                f"Admin affiliation required to change access controls for {entity.label} (id: {entity.id})")
        # Set controls for this specific entity
        await self.access_control_service.set_controls(
            entity,  # Single entity, not aggregate
            control_teams=control_teams,
            release=release,
            user_id=self.user_id
        )
