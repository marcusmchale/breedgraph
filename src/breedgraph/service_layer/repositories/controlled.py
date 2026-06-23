from abc import abstractmethod
from typing import Dict, Set, AsyncGenerator, TypeVar, Generic
from dataclasses import dataclass

from pydantic import BaseModel

from src.breedgraph.service_layer.tracking import TrackableProtocol, TrackedObject
from src.breedgraph.service_layer.repositories.base import BaseRepository, TAggregateInput
from src.breedgraph.custom_exceptions import UnauthorisedOperationError
from src.breedgraph.domain.model.organisations import Access
from src.breedgraph.service_layer.application.access_control import AbstractAccessControlService
from src.breedgraph.domain.model.controls import (
    ReadRelease, ControlledAggregate, ControlledModel, ControlledModelLabel, DiscoveryMatch, Controller
)

TControlledAggregate = TypeVar("TControlledAggregate", bound=ControlledAggregate)


@dataclass(frozen=True)
class ControlledQueryResult(Generic[TControlledAggregate]):
    aggregate: TControlledAggregate
    matches: tuple[DiscoveryMatch, ...] = ()

class ControlledRepository(
    Generic[TAggregateInput, TControlledAggregate],
    BaseRepository[TAggregateInput, TControlledAggregate]
):
    discovery_sensitive_filters: frozenset[str] = frozenset()

    def __init__(
            self,
            controls: AbstractAccessControlService,
            release: ReadRelease = ReadRelease.PRIVATE,
    ):
        super().__init__()
        self.controls = controls

        self.release = release

    @property
    def user_id(self):
        return self.controls.user_id

    @property
    def access_teams(self):
        return self.controls.access_teams

    def _match_allows_discovery(
            self,
            aggregate: TControlledAggregate,
            controllers: Dict[ControlledModelLabel, Dict[int, Controller]],
            match: DiscoveryMatch
    ) -> bool:
        models_by_key = {
            (model.label, model.id): model
            for model in aggregate.controlled_models
        }
        model = models_by_key.get((match.label, match.model_id))
        if model is None:
            return False

        controller = controllers.get(match.label, {}).get(match.model_id)
        if controller is None:
            return False

        return controller.has_access(
            Access.READ,
            user_id=self.user_id,
            access_teams=self.access_teams[Access.READ]
        )

    def _matches_allow_discovery(
            self,
            aggregate: TControlledAggregate,
            controllers: Dict,
            matches: tuple[DiscoveryMatch, ...]
    ) -> bool:
        if not matches:
            return True

        return any(
            self._match_allows_discovery(
                aggregate=aggregate,
                controllers=controllers,
                match=match
            )
            for match in matches
        )

    async def _create(
            self,
            aggregate_input: BaseModel
    ) -> TControlledAggregate:
        if self.controls.user_id is None:
            raise UnauthorisedOperationError("Creation of controlled entities requires a user_id")

        aggregate = await self._create_controlled(aggregate_input)
        await self.controls.set_controls(
            aggregate,
            control_teams=self.access_teams[Access.WRITE],
            release=self.release
        )
        controllers = await self.controls.get_controllers_for_aggregate(aggregate)
        await self.controls.record_writes(aggregate)
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
        result = await self._get_controlled(**kwargs)
        if result is None:
            return None

        aggregate = result.aggregate
        matches = result.matches
        if aggregate is not None:
            controllers = await self.controls.get_controllers_for_aggregate(aggregate)

            if not self._matches_allow_discovery(
                    aggregate=aggregate,
                    controllers=controllers,
                    matches=matches
            ):
                return None

            return aggregate.redacted(
                controllers=controllers,
                user_id=self.user_id,
                read_teams=self.access_teams[Access.READ]
            )
        return None

    @abstractmethod
    async def _get_controlled(self, **kwargs) -> ControlledQueryResult[TControlledAggregate]|None:
        raise NotImplementedError

    async def _get_all(self, **kwargs) -> AsyncGenerator[TControlledAggregate, None]:
        async for result in self._get_all_controlled(**kwargs):
            aggregate = result.aggregate
            matches = result.matches
            if aggregate is not None:
                controllers = await self.controls.get_controllers_for_aggregate(aggregate)

                if not self._matches_allow_discovery(
                        aggregate=aggregate,
                        controllers=controllers,
                        matches=matches
                ):
                    continue

                aggregate = aggregate.redacted(
                    controllers=controllers,
                    user_id=self.user_id,
                    read_teams=self.access_teams[Access.READ]
                )
                if aggregate is not None:
                    yield aggregate

    @abstractmethod
    def _get_all_controlled(self, **kwargs) -> AsyncGenerator[ControlledQueryResult[TControlledAggregate], None]:
        raise NotImplementedError

    async def _remove(self, aggregate: TControlledAggregate):
        if aggregate.protected:
            raise UnauthorisedOperationError(aggregate.protected)
        controllers = await self.controls.get_controllers_for_aggregate(aggregate)
        if not aggregate.can_remove(controllers, self.user_id, self.access_teams[Access.CURATE]):
            raise UnauthorisedOperationError(
                f"Removal requires curate permission"
            )
        await self._remove_controlled(aggregate)

    @abstractmethod
    async def _remove_controlled(self, aggregate: TControlledAggregate):
        raise NotImplementedError

    async def _update(self, aggregate: TControlledAggregate | TrackedObject):
        if not self.controls.user_id:
            raise UnauthorisedOperationError("Changes require a user_id")
        if not aggregate.changed:
            return

        controllers = await self.controls.get_controllers_for_aggregate(aggregate)
        for model in aggregate.removed_models:
            if isinstance(model, ControlledModel):
                controller = controllers[model.label][model.id]
                if not controller.has_access(Access.CURATE, access_teams=self.access_teams[Access.CURATE]):
                    raise UnauthorisedOperationError(f"Removal requires curate permission")

        for model in aggregate.changed_models:
            if isinstance(model, ControlledModel):
                controller = controllers[model.label][model.id]
                if not controller.has_access(Access.CURATE, access_teams=self.access_teams[Access.CURATE]):
                    raise UnauthorisedOperationError(
                        f"Editing requires curate permission")

        await self._update_controlled(aggregate)

        controlled_added = [i for i in aggregate.added_models if isinstance(i, ControlledModel)]
        await self.controls.set_controls(
            controlled_added,
            control_teams=self.access_teams[Access.WRITE],
            release=self.release
        )
        controlled_updates = [i for i in aggregate.changed_models if isinstance(i, ControlledModel)]
        await self.controls.record_writes(controlled_updates + controlled_added)

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
        if not self.controls.user_id:
            raise UnauthorisedOperationError("Changes to access controls require a user_id")
        # Get the current controller for this specific entity
        controller = await self.controls.get_controller(
            entity.label,
            entity.id
        )
        if controller is None:
            raise UnauthorisedOperationError("Controller not found for controlled entity")

        # Check authorization for this specific entity
        if not controller.has_access(Access.ADMIN, access_teams=self.access_teams[Access.ADMIN]):
            raise UnauthorisedOperationError(
                f"Changing access controls requires admin permission")
        # Set controls for this specific entity
        await self.controls.set_controls(
            entity,  # Single entity, not aggregate
            control_teams=control_teams,
            release=release
        )
