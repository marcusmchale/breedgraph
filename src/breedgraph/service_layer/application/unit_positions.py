"""
Units' positions are written here, outside the unit graph aggregate, as germplasm entries are written outside a crop's
pedigree (docs/read-access.md rule 3): moving a batch of samples needs neither their unit graphs loaded nor one request
per unit, and the unit graph repository no longer writes positions, so editing a unit can't undo a move it never saw.
A write takes the write locks of the units first and reads their positions under them (persistence), plans what it
does from them (domain.services.unit_positions) and writes only that, so writes to the same units follow one another.

Changing a unit's positions needs curate access to it, all the units or none; a destination is validated by the
caller, as it reads layouts and the ontology (handlers.commands.unit_graphs).
"""
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Iterable, List

from numpy import datetime64

from breedgraph.custom_exceptions import NoResultFoundError, UnauthorisedOperationError
from breedgraph.domain.model.controls import Access, ControlledModelLabel, ReadRelease
from breedgraph.domain.model.unit_graphs import Position
from breedgraph.domain.services.unit_positions import (
    UnitPositions, PositionWrites, PLACE_FIELDS, plan_move, plan_change, plan_add, plan_remove, named, by_name
)
from breedgraph.service_layer.application.access_control import AbstractAccessControlService
from breedgraph.service_layer.persistence.unit_positions import UnitPositionsPersistenceService

import logging

logger = logging.getLogger(__name__)

# validates a destination: that the user can read its location and layout, and that its coordinates fit the layout
PlaceValidator = Callable[[Position], Awaitable[None]]

UNIT = ControlledModelLabel.UNIT


@dataclass
class ArrivalSelection:
    location_id: int
    start: datetime64 | None = None
    unit_id: int | None = None


class UnitPositionsService:

    def __init__(
            self,
            persistence_service: UnitPositionsPersistenceService,
            access_control_service: AbstractAccessControlService
    ):
        self.persistence = persistence_service
        self.access_control = access_control_service

    @property
    def user_id(self):
        return self.access_control.user_id

    async def selected_unit_ids(self, unit_ids: Iterable[int] | None, arrival: ArrivalSelection | None) -> List[int]:
        """The units given by id, or those of an arrival that the user can read (others stay where they are)"""
        if (unit_ids is None) == (arrival is None):
            raise ValueError("Give the units by id or by arrival, one of the two")
        if unit_ids is not None:
            return list(dict.fromkeys(unit_ids))
        minimum_release = ReadRelease.PUBLIC if self.user_id is None else ReadRelease.REGISTERED
        found = await self.persistence.arrival_unit_ids(
            arrival.location_id, arrival.start, arrival.unit_id,
            read_teams=self.access_control.access_teams[Access.READ], minimum_release=int(minimum_release)
        )
        if not found:
            raise NoResultFoundError("No units you can read arrived there then")
        return found

    async def move_units(self, unit_ids: List[int], position: Position) -> List[int]:
        """
        Moves the units to the position from its start (plan_move); the place is validated by the caller. Returns the
        ids of the units moved, in name order
        """
        units = await self._curated_units(unit_ids)
        await self._write(plan_move(units, position), units)
        return [unit.unit_id for unit in by_name(units)]

    async def change_positions(
            self,
            unit_ids: List[int],
            at: Dict[str, Any],
            change: Dict[str, Any],
            validate_place: PlaceValidator | None = None
    ) -> List[int]:
        """One position of each unit, found by at, given the values in change (plan_change); the ids, in name order"""
        units = await self._curated_units(unit_ids)
        writes = plan_change(units, at, change)
        if validate_place is not None and set(change) & set(PLACE_FIELDS):
            await self._validate_places([position for _, position in writes.changed], validate_place)
        await self._write(writes, units)
        return [unit.unit_id for unit in by_name(units)]

    async def add_position(self, unit_id: int, position: Position) -> None:
        unit, = await self._curated_units([unit_id])
        await self._write(plan_add(unit, position), [unit])

    async def remove_position(self, unit_id: int, position: Position) -> None:
        unit, = await self._curated_units([unit_id])
        await self._write(plan_remove(unit, position), [unit])

    async def _curated_units(self, unit_ids: List[int]) -> List[UnitPositions]:
        """
        The units with their positions, read under their write locks, once the user is known to curate them all: a
        unit they cannot read is reported as not found, by id; those they cannot curate are named
        """
        unit_ids = list(dict.fromkeys(unit_ids))
        if not unit_ids:
            raise ValueError("Give the units whose positions change")
        user_id, teams = self.user_id, self.access_control.access_teams
        controllers = await self.access_control.get_controllers(UNIT, unit_ids)
        hidden = [
            unit_id for unit_id in unit_ids
            if controllers.get(unit_id) is None
            or not controllers[unit_id].has_access(Access.READ, user_id, teams[Access.READ])
        ]
        if hidden:
            raise NoResultFoundError(f"Unit {', '.join(str(unit_id) for unit_id in hidden[:10])} was not found")
        found = await self.persistence.read_positions_locked(unit_ids)
        if len(found) < len(unit_ids):
            raise NoResultFoundError(
                f"Unit {', '.join(str(unit_id) for unit_id in unit_ids if unit_id not in found)} was not found"
            )
        units = [found[unit_id] for unit_id in unit_ids]
        refused = [
            unit for unit in units
            if not controllers[unit.unit_id].has_access(Access.CURATE, user_id, teams[Access.CURATE])
        ]
        if refused:
            raise UnauthorisedOperationError(f"Changing the positions of {named(refused)} requires curate access")
        return units

    @staticmethod
    async def _validate_places(positions: List[Position], validate_place: PlaceValidator) -> None:
        """Each place once: a batch shares its destination"""
        seen = set()
        for position in positions:
            place = (position.location_id, position.layout_id, tuple(str(c) for c in position.coordinates or []))
            if place not in seen:
                seen.add(place)
                await validate_place(position)

    async def _write(self, writes: PositionWrites, units: List[UnitPositions]) -> None:
        await self.persistence.write(writes)
        await self.access_control.record_writes_by_id(UNIT, [unit.unit_id for unit in units])
