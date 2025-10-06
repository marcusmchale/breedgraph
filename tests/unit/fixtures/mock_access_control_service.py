from collections import defaultdict
from numpy import datetime64
from typing import Dict, List, Set


from src.breedgraph.domain.model.controls import Control, ReadRelease, Controller
from src.breedgraph.domain.model.organisations import Access
from src.breedgraph.domain.model.time_descriptors import WriteStamp
from src.breedgraph.service_layer.application.access_control import AbstractAccessControlService


class MockAccessControlService(AbstractAccessControlService):
    """
    Test implementation of access control service for integration testing.
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
        self._access_teams: Dict[int, Dict[Access, Set[int]]] = {}
        self.user_id: int|None = None
        self.access_teams: Dict[Access, Set[int]] = {}

    async def _set_controls(
            self,
            label: str,
            model_ids: Set[int] | List[int],
            team_ids: Set[int] | List[int],
            user_id: int,
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
                    team_id=team_id,
                    release=release,
                    time=datetime64('now')
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
        write_stamp = WriteStamp(user=user_id, time=datetime64('now'))

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

    def get_access_teams(self, user_id: int = None) -> Dict[Access, Set[int]]:
        """Get access teams for a user"""
        if user_id is None:
            return {a: set() for a in Access}

        return self._access_teams.get(user_id, {a: set() for a in Access})

    def set_test_access_teams(self, user_id: int|None, access_teams: Dict[Access, Set[int]]):
        """Test helper to set access teams"""
        self._access_teams[user_id] = access_teams

    def clear_test_data(self):
        """Clear all test data - useful for test cleanup"""
        self._controls.clear()
        self._writes.clear()
        self._access_teams.clear()

    async def initialize_user_context(self, user_id: int|None) -> None:
        self.user_id = user_id
        self.access_teams = {a: set() for a in Access}
        if user_id is not None:
            self.access_teams.update(self.get_access_teams(user_id))
