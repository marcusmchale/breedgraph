from abc import ABC, abstractmethod
from collections import defaultdict

from typing import Dict, List, Set, Optional
from datetime import datetime

from neo4j import AsyncTransaction

from src.breedgraph.domain.model.controls import (
    Control, WriteStamp, ControlledModel, ControlledAggregate, Controller, ReadRelease
)
from src.breedgraph.adapters.repositories.trackable_wrappers import Tracked
from src.breedgraph.custom_exceptions import IllegalOperationError
from src.breedgraph.adapters.neo4j.cypher.query_builders import controls

import logging

logger = logging.getLogger(__name__)


class AbstractControllersService(ABC):
    """
    Service for managing controllers
    """
    @staticmethod
    async def _parse_input_to_models_by_label(
            input_: List[ControlledModel] | List[ControlledAggregate] | ControlledModel | ControlledAggregate
    ) -> Dict[str, List[ControlledModel]]:
        controlled_models = list()
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

        models_by_label: Dict[str, List[ControlledModel]] = {}
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
            release: ReadRelease
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
                release=release
            )

    @abstractmethod
    async def _set_controls(
            self,
            label: str,
            model_ids: Set[int]|List[int],
            team_ids: Set[int]|List[int],
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
            label: str,
            model_ids: Set[int]|List[int],
            user_id: int
    ) -> None:
        """Record write stamps for multiple entities - batch operation"""
        raise NotImplementedError

    async def get_controller(self, label: str, model_id: int) -> Optional[Controller]:
        """Get controller by label and model_id"""
        controllers = await self._get_controllers(label, [model_id])
        return controllers.get(model_id)

    async def get_controllers(self, label: str, model_ids: List[int]) -> Dict[int, Controller]:
        """
        Get multiple controllers by label and model_ids
        """
        return await self._get_controllers(label, model_ids)

    async def get_controllers_for_aggregate(self, aggregate: ControlledAggregate) -> Dict[str, Dict[int, Controller]]:
        """
        :param aggregate:
        :return: Dict keyed by label, the model_id to controller
        """
        label_model_ids = defaultdict(list)
        for model in aggregate.controlled_models:
            label_model_ids[model.label].append(model.id)
        # We fetch controllers for removed models to handle the logic around control over committing a removal
        if isinstance(aggregate, Tracked):
            for model in aggregate.removed_models:
                label_model_ids[model.label].append(model.id)
        return {
            label: await self.get_controllers(label, model_ids) for label, model_ids in label_model_ids.items()
        }

    # Abstract methods for concrete implementations
    @abstractmethod
    async def _get_controllers(self, label: str, model_ids: List[int]) -> Dict[int, Controller]:
        """Get controllers for multiple model instances - key batch operation"""
        raise NotImplementedError

    @abstractmethod
    async def remove_controls(self, label: str, model_ids: List[int], team_id: int) -> None:
        """Remove a specific team's control from multiple models - batch operation"""
        raise NotImplementedError



class Neo4jControllersService(AbstractControllersService):

    def __init__(
            self,
            tx: AsyncTransaction
    ):
        super().__init__()
        self.tx = tx
        self.plurals_by_label: Dict[str, str] = {}


    async def _set_controls(
            self,
            label: str,
            model_ids: Set[int]|List[int],
            team_ids: Set[int]|List[int],
            release: ReadRelease
    ) -> None:
        if not model_ids:
            return

        await self.tx.run(
            controls.set_controls(label=label),
            entity_ids=model_ids if isinstance(model_ids, list) else list(model_ids),
            team_ids=team_ids if isinstance(team_ids, list) else list(team_ids),
            release=release.value
        )

    async def _record_writes(
            self,
            label: str,
            model_ids: Set[int]|List[int],
            user_id: int
    ) -> None:
        if not model_ids:
            return

        await self.tx.run(
            controls.record_writes(label=label),
            entity_ids=model_ids if isinstance(model_ids, list) else list(model_ids),
            user_id=user_id,
        )

    async def _get_controllers(self, label: str, model_ids: Set[int]|List[int]) -> Dict[int, Controller]:
        if not model_ids:
            return {}

        result = await self.tx.run(
            controls.get_controllers(label=label),
            entity_ids=model_ids
        )

        controllers = {}
        async for record in result:
            entity_id = record['entity_id']
            control_map = {
                control['team']: Control(release=control['release'], time=control['time'])
                for control in record['controls']
            }
            writes = [
                WriteStamp(user=writes['user'], time=writes['time'])
                for writes in record['writes']
            ]
            controllers[entity_id] = Controller(controls=control_map, writes=writes)
        return controllers

    async def remove_controls(self, label: str, model_ids: Set[int]|List[int], team_ids: Set[int]|List[int]) -> None:
        if not model_ids:
            return

        await self.tx.run(
            controls.remove_controls(label=label),
            entity_ids=model_ids,
            team_ids=team_ids
        )


class TestControllersService(AbstractControllersService):
    """
    Test implementation of controllers service for integration testing.
    Stores data in memory without requiring database operations.
    """

    def __init__(
            self
    ):
        super().__init__()
        # In-memory storage for test data
        self._controls: Dict[str, Dict[int, Dict[int, Control]]] = defaultdict(
            lambda: defaultdict(dict))  # label -> model_id -> team_id -> Control
        self._writes: Dict[str, Dict[int, List[WriteStamp]]] = defaultdict(
            lambda: defaultdict(list))  # label -> model_id -> [WriteStamp]

    async def _set_controls(
            self,
            label: str,
            model_ids: Set[int] | List[int],
            team_ids: Set[int] | List[int],
            release: ReadRelease
    ) -> None:
        """Create controls for multiple entities - batch operation"""
        if not model_ids:
            return

        model_ids_list = model_ids if isinstance(model_ids, list) else list(model_ids)
        team_ids_list = team_ids if isinstance(team_ids, list) else list(team_ids)

        for model_id in model_ids_list:
            for team_id in team_ids_list:
                self._controls[label][model_id][team_id] = Control(
                    release=release,
                    time=datetime.now()
                )

    async def _record_writes(
            self,
            label: str,
            model_ids: Set[int] | List[int],
            user_id: int
    ) -> None:
        """Record write stamps for multiple entities - batch operation"""
        if not model_ids:
            return

        model_ids_list = model_ids if isinstance(model_ids, list) else list(model_ids)
        write_stamp = WriteStamp(user=user_id, time=datetime.now())

        for model_id in model_ids_list:
            self._writes[label][model_id].append(write_stamp)

    async def _get_controllers(self, label: str, model_ids: List[int]) -> Dict[int, Controller]:
        """Get controllers for multiple model instances - key batch operation"""
        if not model_ids:
            return {}

        controllers = {}
        for model_id in model_ids:
            controls_map = self._controls[label].get(model_id, {})
            writes_list = self._writes[label].get(model_id, [])

            if controls_map or writes_list:
                controllers[model_id] = Controller(
                    controls=controls_map,
                    writes=writes_list
                )

        return controllers

    async def remove_controls(self, label: str, model_ids: List[int], team_ids: List[int]) -> None:
        """Remove a specific team's control from multiple models - batch operation"""
        if not model_ids:
            return

        team_ids_list = team_ids if isinstance(team_ids, list) else [team_ids]

        for model_id in model_ids:
            if model_id in self._controls[label]:
                for team_id in team_ids_list:
                    self._controls[label][model_id].pop(team_id, None)

    def clear_test_data(self):
        """Clear all test data - useful for test cleanup"""
        self._controls.clear()
        self._writes.clear()
