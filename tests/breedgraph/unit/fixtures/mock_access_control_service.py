from collections import defaultdict
from numpy import datetime64
from typing import Dict, List, Set


from breedgraph.domain.model.controls import Control, ReadRelease, Controller
from breedgraph.domain.model import Access
from breedgraph.domain.model.time_descriptors import WriteStamp
from breedgraph.domain.model.control_transfers import ControlTransferInput, ControlTransferStored
from breedgraph.service_layer.application.access_control import AbstractAccessControlService


class MockAccessControlService(AbstractAccessControlService):
    """
    Test implementation of access control service for integration testing.
    Stores data in memory without requiring database operations.
    """
    _access_teams: Dict[int, Dict[Access, Set[int]]] = {}

    def __init__(
            self,
            user_id: int|None = None
    ):
        super().__init__()
        self.user_id = user_id
        # In-memory storage for test data
        self._controls: Dict[str, Dict[int, Dict[int, Control]]] = defaultdict(
            lambda: defaultdict(dict))  # label -> model_id -> team_id -> Control
        self._writes: Dict[str, Dict[int, List[WriteStamp]]] = defaultdict(
            lambda: defaultdict(list))  # label -> model_id -> [WriteStamp]
        self.access_teams = self.load_access_teams(user_id)
        self._transfers: Dict[int, ControlTransferStored] = dict()
        self._team_descendants: Dict[int, Set[int]] = dict()

    @classmethod
    async def create(cls, user_id: int|None = None):
        return cls(user_id=user_id)

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
                    time=datetime64('now'),
                    user_id=user_id
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

    async def _add_controls(
            self,
            label: str,
            model_ids: List[int],
            team_ids: Set[int] | List[int],
            release: ReadRelease,
            user_id: int
    ) -> None:
        for model_id in model_ids:
            for team_id in team_ids:
                self._controls[label][model_id][team_id] = Control(
                    team_id=team_id,
                    release=release,
                    time=datetime64('now'),
                    user_id=user_id
                )

    async def _end_controls(
            self,
            label: str,
            model_ids: List[int],
            team_ids: Set[int] | List[int],
            user_id: int
    ) -> None:
        for model_id in model_ids:
            for team_id in team_ids:
                self._controls[label][model_id].pop(team_id, None)

    def set_test_team_descendants(self, team_id: int, descendants: Set[int]):
        self._team_descendants[team_id] = set(descendants)

    async def _get_team_and_descendants(self, team_id: int) -> Set[int]:
        return {team_id} | self._team_descendants.get(team_id, set())

    async def _create_transfer(self, transfer: ControlTransferInput) -> ControlTransferStored:
        stored = ControlTransferStored(
            id=len(self._transfers) + 1,
            entities=list(transfer.entities),
            from_teams=list(transfer.from_teams),
            recipient_team=transfer.recipient_team,
            keep_from_teams=transfer.keep_from_teams,
            offered_by=transfer.offered_by
        )
        self._transfers[stored.id] = stored
        return stored

    async def _get_transfer(self, transfer_id: int) -> ControlTransferStored | None:
        return self._transfers.get(transfer_id)

    async def _get_transfers(self, recipient_teams=None, from_teams=None, statuses=None) -> List[ControlTransferStored]:
        return [
            transfer for transfer in self._transfers.values()
            if (recipient_teams is None or transfer.recipient_team in recipient_teams)
            and (from_teams is None or set(transfer.from_teams).intersection(from_teams))
            and (statuses is None or transfer.status in statuses)
        ]

    async def _set_transfer(self, transfer: ControlTransferStored) -> ControlTransferStored:
        self._transfers[transfer.id] = transfer
        return transfer

    def load_access_teams(self, user_id: int|None = None) -> Dict[Access, Set[int]]:
        """Get access teams for a user"""
        if user_id is None:
            return {a: set() for a in Access}

        return self._access_teams.get(user_id, {a: set() for a in Access})

    def set_test_access_teams(self, user_id: int, access_teams: Dict[Access, Set[int]]):
        """Test helper to set access teams"""
        self._access_teams[user_id] = access_teams

    def clear_test_data(self):
        """Clear all test data - useful for test cleanup"""
        self._controls.clear()
        self._writes.clear()
        self._access_teams.clear()

    async def _change_user_context(self, user_id: int | None) -> None:
        self.user_id = user_id
        self.access_teams = {a: set() for a in Access}
        if user_id is not None:
            self.access_teams.update(self.load_access_teams(user_id))
