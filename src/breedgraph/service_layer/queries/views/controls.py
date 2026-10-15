from abc import ABC, abstractmethod

from breedgraph.domain.model.controls import Controller, ControlledModelLabel

from typing import Dict, List


class AbstractControlsView(ABC):
    """
    Controllers as the user may see them: the full controller of an entity they can read, and for one they cannot,
    a placeholder with its controls alone (whom to ask for access), without the history of writes to it.
    """
    user_id: int | None
    read_teams: List[int]

    async def get_controllers(self, label: ControlledModelLabel, entity_ids: List[int]) -> Dict[int, Controller]:
        """The controllers of the entities with these ids that exist, by entity id"""
        entity_ids = [int(entity_id) for entity_id in dict.fromkeys(entity_ids) if entity_id is not None]
        if not entity_ids:
            return {}
        return await self._get_controllers(label, entity_ids)

    @abstractmethod
    async def _get_controllers(self, label: ControlledModelLabel, entity_ids: List[int]) -> Dict[int, Controller]:
        ...
