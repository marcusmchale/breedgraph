from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from breedgraph.custom_exceptions import UnauthorisedOperationError
from breedgraph.domain.model.controls import Controller, ControlledModelLabel, ReadRelease
from breedgraph.domain.model.unit_graphs import UnitOutput

from typing import Dict, List, Iterable


@dataclass
class ControlledCount:
    """How many entities of a label a team controls at a release"""
    team_id: int
    label: ControlledModelLabel
    release: ReadRelease
    count: int


@dataclass
class ControlledItem:
    """An entity a team controls: its name (REDACTED where the user cannot read it), the team's release, and context"""
    label: ControlledModelLabel
    id: int
    name: str | None
    release: ReadRelease
    other_team_ids: List[int] = field(default_factory=list)
    context: str | None = None  # the name of what holds it, e.g. a dataset's study


@dataclass
class ControlledItems:
    total: int
    items: List[ControlledItem]


@dataclass
class ControlledUnitNode:
    """A unit in the tree of what a team controls, which the team controls (release) or holds units it does"""
    unit: UnitOutput  # id, name, subject and germplasm only: its place in the tree is the node's
    parent_id: int | None  # the unit it was found below, None for a unit graph root
    count: int  # the units the team controls, this one and those below it
    release: ReadRelease | None  # the team's release, None where it doesn't control the unit itself
    other_team_ids: List[int] = field(default_factory=list)


class AbstractControlsView(ABC):
    """
    Controllers as the user may see them: the full controller of an entity they can read, and for one they cannot,
    a placeholder with its controls alone (whom to ask for access), without the history of writes to it.

    And what a team controls, for the team's admins only, as controls are an admin concern: how many entities of each
    label, the entities of a label a page at a time, and the units as a tree from the roots of their unit graphs.
    """
    user_id: int | None
    read_teams: List[int]

    async def get_controllers(self, label: ControlledModelLabel, entity_ids: List[int]) -> Dict[int, Controller]:
        """The controllers of the entities with these ids that exist, by entity id"""
        entity_ids = [int(entity_id) for entity_id in dict.fromkeys(entity_ids) if entity_id is not None]
        if not entity_ids:
            return {}
        return await self._get_controllers(label, entity_ids)

    async def _require_admin(self, team_ids: Iterable[int]) -> None:
        """Refuses teams the user is not an admin of, rather than leave them out, so the client can say why"""
        admin_teams = set(await self._get_admin_teams())
        refused = sorted({int(team_id) for team_id in team_ids} - admin_teams)
        if refused:
            raise UnauthorisedOperationError(f"Admin access is required to see what teams {refused} control")

    async def get_controlled_counts(self, team_ids: List[int]) -> List[ControlledCount]:
        team_ids = [int(team_id) for team_id in dict.fromkeys(team_ids)]
        await self._require_admin(team_ids)
        return await self._get_controlled_counts(team_ids) if team_ids else []

    async def get_controlled_entities(
            self,
            team_id: int,
            label: ControlledModelLabel,
            release: ReadRelease | None = None,
            offset: int = 0,
            limit: int = 50
    ) -> ControlledItems:
        """The entities of a label the team controls, by id, a page at a time"""
        await self._require_admin([team_id])
        return await self._get_controlled_entities(int(team_id), label, release, max(0, offset), max(0, limit))

    async def get_controlled_units(self, team_id: int, parent_ids: List[int] | None = None) -> List[ControlledUnitNode]:
        """
        Without parent_ids, the roots of the unit graphs holding units the team controls; with them, the nearest units
        below each (readable, or controlled by the team) that are or hold units the team controls
        """
        await self._require_admin([team_id])
        if parent_ids is None:
            return await self._get_controlled_unit_roots(int(team_id))
        parent_ids = [int(parent_id) for parent_id in dict.fromkeys(parent_ids)]
        return await self._get_controlled_unit_children(int(team_id), parent_ids) if parent_ids else []

    @abstractmethod
    async def _get_admin_teams(self) -> List[int]:
        ...

    @abstractmethod
    async def _get_controllers(self, label: ControlledModelLabel, entity_ids: List[int]) -> Dict[int, Controller]:
        ...

    @abstractmethod
    async def _get_controlled_counts(self, team_ids: List[int]) -> List[ControlledCount]:
        ...

    @abstractmethod
    async def _get_controlled_entities(
            self, team_id: int, label: ControlledModelLabel, release: ReadRelease | None, offset: int, limit: int
    ) -> ControlledItems:
        ...

    @abstractmethod
    async def _get_controlled_unit_roots(self, team_id: int) -> List[ControlledUnitNode]:
        ...

    @abstractmethod
    async def _get_controlled_unit_children(self, team_id: int, parent_ids: List[int]) -> List[ControlledUnitNode]:
        ...
