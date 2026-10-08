from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Iterable
from breedgraph.service_layer.tracking.wrappers import is_tracked_object

from breedgraph.domain.model.controls import (
    ControlledModel, ControlledAggregate, Controller, ReadRelease, Access, ControlledModelLabel
)
from breedgraph.custom_exceptions import IllegalOperationError, UnauthorisedOperationError

from typing import Dict, List, Set, Optional

import logging
logger = logging.getLogger(__name__)


class AbstractAccessControlService(ABC):
    """
    Service for managing controls over stored entities
    """
    user_id: int | None
    access_teams: Dict[Access, Set[int]]

    @staticmethod
    async def _parse_input_to_models_by_label(
            input_: Iterable[ControlledModel] | Iterable[ControlledAggregate] | ControlledModel | ControlledAggregate
    ) -> Dict[ControlledModelLabel, Iterable[ControlledModel]]:
        controlled_models = []

        if isinstance(input_, Iterable) and not is_tracked_object(input_):
            # if is tracked object can still pass as an iterable then fail because it doesn't have an iter method
            # this is just because of object proxy so check is_tracked_object and revert to single element processing.
            for i in input_:
                if isinstance(i, ControlledAggregate):
                    controlled_models.extend(i.controlled_models)
                elif isinstance(i, ControlledModel):
                    controlled_models.append(i)
        else:
            if isinstance(input_, ControlledAggregate):
                controlled_models = input_.controlled_models
            elif isinstance(input_, ControlledModel):
                controlled_models = [input_]

        models_by_label: Dict[ControlledModelLabel, list[ControlledModel]] = {}
        for model in controlled_models:
            # exclude input models
            if not hasattr(model, 'id') or not model.id:
                continue

            if model.label not in models_by_label:
                models_by_label[model.label] = []
            models_by_label[model.label].append(model)
        return models_by_label

    async def set_controls(
            self,
            models: Iterable[ControlledModel] | Iterable[ControlledAggregate] | ControlledModel | ControlledAggregate,
            control_teams: Set[int],
            release: ReadRelease
    ) -> None:
        """Set controls for all controlled models either supplied as a singleton, as a list or in an aggregate or list of aggregates"""

        if not models:
            return

        models_by_label = await self._parse_input_to_models_by_label(models)
        for label, models in models_by_label.items():
            model_ids = [model.id for model in models]
            await self._verify_and_set_controls(
                label=label,
                model_ids=model_ids,
                control_teams=control_teams,
                release=release
            )

    async def _verify_and_set_controls(
            self,
            label: ControlledModelLabel,
            model_ids: Iterable[int],
            control_teams: set[int],
            release: ReadRelease
    ):
        if not self.user_id:
            raise IllegalOperationError("User ID required to set controls")
        if not control_teams:
            raise IllegalOperationError("Control teams required to set controls")

        controllers = await self.get_controllers(label, model_ids)

        for model_id, controller in controllers.items():
            if not controller.has_access(Access.ADMIN, self.user_id, access_teams=control_teams):
                raise UnauthorisedOperationError("Admin access is required to set controls")

        # for models with existing controllers we need to filter out control teams provided that are not already in the controller.
        # this is per model so if we want to batch process we need to either split or do it in the query.
        await self._set_controls(
            label=label,
            model_ids=model_ids,
            team_ids=control_teams,
            release=release,
            user_id=self.user_id
        )

    async def set_controls_by_id_and_label(
            self,
            ids: Iterable[int],
            label: ControlledModelLabel,
            control_teams: Set[int],
            release: ReadRelease
    ):
        await self._verify_and_set_controls(label=label, model_ids=ids, control_teams=control_teams, release=release)

    @abstractmethod
    async def _set_controls(
            self,
            label: ControlledModelLabel,
            model_ids: Iterable[int],
            team_ids: Iterable[int],
            release: ReadRelease,
            user_id: int
    ) -> None:
        """Set controls for multiple entities - batch operation"""
        ...

    async def record_writes(
            self,
            models: Iterable[ControlledModel] | Iterable[ControlledAggregate] | ControlledModel | ControlledAggregate
    ) -> None:
        """Record write stamp on all controlled models either supplied as a singleton, as a list or in an aggregate or list of aggregates"""
        if not models:
            return

        if self.user_id is None:
            raise IllegalOperationError("User id required to record writes")

        models_by_label = await self._parse_input_to_models_by_label(models)

        # Create write stamps using batch operations
        for label, models in models_by_label.items():
            model_ids = [model.id for model in models]
            await self._record_writes(
                label=label,
                model_ids=model_ids,
                user_id=self.user_id
            )

    @abstractmethod
    async def _record_writes(
            self,
            label: ControlledModelLabel,
            model_ids: Iterable[int],
            user_id: int
    ) -> None:
        """Record write stamps for multiple entities - batch operation"""
        ...

    async def get_controller(self, label: ControlledModelLabel, model_id: int) -> Optional[Controller]:
        """Get controller by label and model_id"""
        controllers = await self._get_controllers(label, [model_id])
        return controllers.get(model_id)

    async def get_controllers(self, label: ControlledModelLabel, model_ids: Iterable[int]) -> Dict[int, Controller]:
        """
        Get multiple controllers by label and model_ids
        """
        return await self._get_controllers(label, model_ids)

    async def get_controllers_for_aggregate(self, aggregate: ControlledAggregate) -> Dict[ControlledModelLabel, Dict[int, Controller]]:
        """
        :param aggregate:
        :return: Dict keyed by label, the model_id to controller
        """
        label_model_ids = defaultdict(list)
        for model in aggregate.controlled_models:
            label_model_ids[model.label].append(model.id)
        controllers = {
            label: await self.get_controllers(label, model_ids)
            for label, model_ids in label_model_ids.items()
        }
        return controllers

    # Abstract methods for concrete implementations
    @abstractmethod
    async def _get_controllers(self, label: ControlledModelLabel, model_ids: Iterable[int]) -> Dict[int, Controller]:
        """Get controllers for multiple model instances - key batch operation"""
        ...

    async def add_controls(
            self,
            label: ControlledModelLabel,
            model_ids: Iterable[int],
            team_ids: Set[int],
            release: ReadRelease
    ) -> None:
        """
        Add control teams to existing models.
        Callers are responsible for authorising the change, e.g. through an accepted control transfer.
        """
        if not self.user_id:
            raise IllegalOperationError("User ID required to add controls")
        if not team_ids:
            raise IllegalOperationError("Control teams required to add controls")

        model_ids = list(model_ids)
        controllers = await self.get_controllers(label, model_ids)
        for model_id in model_ids:
            controller = controllers.get(model_id)
            if controller is None:
                raise IllegalOperationError(f"No controls found for {label} {model_id}")
            if controller.teams.intersection(team_ids):
                raise IllegalOperationError(f"Teams already control {label} {model_id}")

        await self._add_controls(
            label=label,
            model_ids=model_ids,
            team_ids=team_ids,
            release=release,
            user_id=self.user_id
        )

    @abstractmethod
    async def _add_controls(
            self,
            label: ControlledModelLabel,
            model_ids: Iterable[int],
            team_ids: Iterable[int],
            release: ReadRelease,
            user_id: int
    ) -> None:
        ...

    async def end_controls(
            self,
            label: ControlledModelLabel,
            model_ids: Iterable[int],
            team_ids: Set[int]
    ) -> None:
        """
        End the control of teams over existing models. The ended controls are kept as history.
        At least one control team must remain for each model.
        Callers are responsible for authorising the change, e.g. through an accepted control transfer.
        """
        if not self.user_id:
            raise IllegalOperationError("User ID required to end controls")
        if not team_ids:
            raise IllegalOperationError("Control teams required to end controls")

        model_ids = list(model_ids)
        controllers = await self.get_controllers(label, model_ids)
        for model_id in model_ids:
            controller = controllers.get(model_id)
            if controller is None:
                raise IllegalOperationError(f"No controls found for {label} {model_id}")
            if not team_ids.issubset(controller.teams):
                raise IllegalOperationError(f"Teams do not control {label} {model_id}")
            if not controller.teams - team_ids:
                raise IllegalOperationError(f"At least one control team must remain for {label} {model_id}")

        await self._end_controls(
            label=label,
            model_ids=model_ids,
            team_ids=team_ids,
            user_id=self.user_id
        )

    @abstractmethod
    async def _end_controls(
            self,
            label: ControlledModelLabel,
            model_ids: Iterable[int],
            team_ids: Iterable[int],
            user_id: int
    ) -> None:
        ...

