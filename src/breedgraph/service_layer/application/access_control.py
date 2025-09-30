from abc import ABC, abstractmethod
from collections import defaultdict

from src.breedgraph.domain.model.controls import (
    ControlledModel, ControlledAggregate, Controller, ReadRelease, Access, ControlledModelLabel
)
from src.breedgraph.domain.events import Event
from src.breedgraph.custom_exceptions import IllegalOperationError


from typing import Dict, List, Set, Optional

import logging
logger = logging.getLogger(__name__)


class AbstractAccessControlService(ABC):
    """
    Service for managing controls over stored entities
    """
    def __init__(self):
        self.events: List[Event] = []
        self.user_id: int | None = None
        self.access_teams: Dict[Access, Set[int]] | None = None

    def collect_events(self):
        while self.events:
            yield self.events.pop(0)

    @staticmethod
    async def _parse_input_to_models_by_label(
            input_: List[ControlledModel] | List[ControlledAggregate] | ControlledModel | ControlledAggregate
    ) -> Dict[ControlledModelLabel, List[ControlledModel]]:
        controlled_models = []
        if isinstance(input_, list):
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

        models_by_label: Dict[ControlledModelLabel, List[ControlledModel]] = {}
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
            models: List[ControlledModel] | List[ControlledAggregate] | ControlledModel | ControlledAggregate,
            control_teams: Set[int],
            release: ReadRelease,
            user_id: int
    ) -> None:
        """Set controls for all controlled models either supplied as a singleton, as a list or in an aggregate or list of aggregates"""
        if not models:
            return

        if not control_teams:
            raise IllegalOperationError("Control teams required to set controls")

        models_by_label = await self._parse_input_to_models_by_label(models)

        # Create/Set controllers using batch operations
        for label, models in models_by_label.items():
            model_ids = [model.id for model in models]
            await self._set_controls(
                label=label,
                model_ids=model_ids,
                team_ids=control_teams,
                release=release,
                user_id=user_id
            )

    async def set_controls_by_id_and_label(self, ids: List[int], label: ControlledModelLabel, control_teams: Set[int], release: ReadRelease, user_id: int):
        if not ids:
            return
        if not control_teams:
            raise IllegalOperationError("Control teams required to set controls")

        await self._set_controls(
            label=label,
            model_ids=ids,
            team_ids=control_teams,
            release=release,
            user_id=user_id
        )

    @abstractmethod
    async def _set_controls(
            self,
            label: ControlledModelLabel,
            model_ids: Set[int]|List[int],
            team_ids: Set[int]|List[int],
            user_id: int,
            release: ReadRelease
    ) -> None:
        """Set controls for multiple entities - batch operation"""
        raise NotImplementedError

    async def record_writes(
            self,
            models: List[ControlledModel] | List[ControlledAggregate] | ControlledModel | ControlledAggregate,
            user_id: int
    ) -> None:
        """Record write stamp on all controlled models either supplied as a singleton, as a list or in an aggregate or list of aggregates"""
        if not models:
            return

        if user_id is None:
            raise IllegalOperationError("User id required to record writes")

        models_by_label = await self._parse_input_to_models_by_label(models)

        # Create write stamps using batch operations
        for label, models in models_by_label.items():
            model_ids = [model.id for model in models]
            await self._record_writes(
                label=label,
                model_ids=model_ids,
                user_id=user_id
            )

    @abstractmethod
    async def _record_writes(
            self,
            label: ControlledModelLabel,
            model_ids: Set[int]|List[int],
            user_id: int
    ) -> None:
        """Record write stamps for multiple entities - batch operation"""
        raise NotImplementedError

    async def get_controller(self, label: ControlledModelLabel, model_id: int) -> Optional[Controller]:
        """Get controller by label and model_id"""
        controllers = await self._get_controllers(label, [model_id])
        return controllers.get(model_id)

    async def get_controllers(self, label: ControlledModelLabel, model_ids: List[int]) -> Dict[int, Controller]:
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

    async def initialize_user_context(self, user_id: int|None) -> None:
        self.user_id = user_id
        self.access_teams = {
            a: set() for a in Access
        }
        if user_id is not None:
            self.access_teams.update(await self.get_access_teams(user_id))


    # Abstract methods for concrete implementations
    @abstractmethod
    async def _get_controllers(self, label: ControlledModelLabel, model_ids: List[int]) -> Dict[int, Controller]:
        """Get controllers for multiple model instances - key batch operation"""
        ...

    @abstractmethod
    async def remove_controls(self, label: ControlledModelLabel, model_ids: List[int], team_id: int) -> None:
        """Remove a specific team's control from multiple models - batch operation"""
        ...

    @abstractmethod
    async def get_access_teams(self, user_id: int = None) -> Dict[Access, Set[int]]:
        """Get access teams for a user"""
        ...



