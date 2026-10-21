"""
Where the units of records were, for position grouping (docs/analysis.md §3).

A position counts for the grouping when its location is, or is below, a location of one of the location types and,
when axes are configured, it is in a layout with a value on each axis, from its own layout or one above it in the
layout tree. Its place is the nearest such location and the axis values, each with the layout that has the axis.

A record is placed by the nearest unit with a position that counts: its own unit, or else the nearest units above it,
one on each lineage (domain.services.lineages), whose places must agree. So a sample in a lab is placed by its tree
unless the lab is of one of the types. With subjects, a unit below a unit of one of them starts from that unit, so the
units in between don't count, e.g. a sample analysed in a lab abroad is placed in its tree's country.

Positions count at any time: of a unit's positions that count, the one holding at the record's time (or the grouping's
time) places it, the later-starting one after a move, as the Units pages show it; without a time, or when none of them
holds then, they must give the same place.

What the user cannot see stops a placement (docs/read-access.md, rule 3): a hidden unit with positions, or a position at
a location or in a layout the user cannot read, gives no place, since one from further up could be wrong.
"""
from dataclasses import dataclass
from typing import Union

from numpy import datetime64

from breedgraph.domain.model.analysis import PositionGrouping, intervals_overlap
from breedgraph.domain.model.analysis_context import AnalysisContext, AnalysisRecord, LocationContext, LayoutContext, UnitContext
from breedgraph.domain.model.time_descriptors import upper
from breedgraph.domain.model.unit_graphs import Position
from breedgraph.domain.services.lineages import nearest_on_each_lineage


@dataclass(frozen=True)
class Place:
    """
    The levels of the position dimensions of a record: the location, and each configured axis as (axis, the layout
    with the axis, value), in the order of the grouping's axes
    """
    location_id: int
    axes: tuple[tuple[str, int, str], ...] = ()


class _Unknown:
    """A place the user cannot see"""
    def __repr__(self):
        return 'UNKNOWN'

UNKNOWN = _Unknown()

Candidates = Union[list[tuple[Position, Union[Place, _Unknown]]], _Unknown, None]

# for ordering positions as the API lists them
EARLIEST = datetime64('0001-01-01T00:00:00', 'ms')
LATEST = datetime64('9999-12-31T23:59:59', 'ms')


def position_order(position: Position) -> tuple[datetime64, datetime64]:
    """By start, those without one first, then by end, those without one last"""
    start = EARLIEST if position.start is None else datetime64(position.start, 'ms')
    end = LATEST if position.end is None else datetime64(upper(position.end), 'ms')
    return start, end


class Placer:

    def __init__(self, grouping: PositionGrouping, context: AnalysisContext):
        self.types = set(grouping.location_type_ids)
        self.subjects = set(grouping.subject_ids)
        self.axes = list(grouping.axes)
        self.time = grouping.time
        self.units = context.units
        self.locations = context.locations
        self.layouts = context.layouts
        self.hidden = context.hidden_positioned
        self._typed: dict[int, int | None] = {}
        self._candidates: dict[int, Candidates] = {}
        self._places: dict[tuple, Place | None] = {}

    def place(self, record: AnalysisRecord) -> Place | None:
        """Where the record's unit was, or None if it can't be placed (a placeholder of a hidden unit never is)"""
        unit = record.unit
        if unit is None or not unit.readable:
            return None
        if self.time is not None:
            start = end = self.time
        else:
            start = record.start if record.start is not None else record.end
            end = record.end if record.end is not None else record.start
        key = (unit.unit_id, start, end)
        if key not in self._places:
            self._places[key] = self._place(unit, start, end)
        return self._places[key]

    def _place(self, unit: UnitContext, start: datetime64 | None, end: datetime64 | None) -> Place | None:
        places = set()
        for origin in self._origins(unit):
            if self._candidates_of(origin) is not None:
                sources = [origin]
            else:
                sources = nearest_on_each_lineage(
                    origin, self._place_parents, lambda unit_id: self._candidates_of(unit_id) is not None
                )
            for source in sources:
                place = self._choose(self._candidates_of(source), start, end)
                if place is None or place is UNKNOWN:
                    return None
                places.add(place)
        return places.pop() if len(places) == 1 else None

    def _origins(self, unit: UnitContext) -> list[int]:
        """Where a placement starts: the unit, or with subjects the nearest units of them above it, one on each lineage"""
        if not self.subjects or unit.subject_id in self.subjects:
            return [unit.unit_id]
        found = nearest_on_each_lineage(unit.unit_id, self._parents, self._is_subject)
        return found or [unit.unit_id]

    def _is_subject(self, unit_id: int) -> bool:
        unit = self.units.get(unit_id)
        return unit is not None and unit.subject_id in self.subjects

    def _parents(self, unit_id: int) -> list[int]:
        unit = self.units.get(unit_id)
        return unit.parent_ids if unit is not None else []

    def _place_parents(self, unit_id: int) -> list[int]:
        unit = self.units.get(unit_id)
        return unit.place_parent_ids if unit is not None else []

    def _candidates_of(self, unit_id: int) -> Candidates:
        """A unit's positions that count with their places, UNKNOWN for a hidden unit with positions, or None"""
        if unit_id not in self._candidates:
            self._candidates[unit_id] = self._find_candidates(unit_id)
        return self._candidates[unit_id]

    def _find_candidates(self, unit_id: int) -> Candidates:
        if unit_id in self.hidden:
            return UNKNOWN
        unit = self.units.get(unit_id)
        if unit is None or not unit.readable:
            return None
        found = []
        for position in unit.positions:
            place = self._place_of(position)
            if place is not None:
                found.append((position, place))
        return found or None

    @staticmethod
    def _choose(candidates: Candidates, start: datetime64 | None, end: datetime64 | None) -> Place | _Unknown | None:
        """The place of the position holding at the time, the later-starting after a move; else the one they agree on"""
        if candidates is UNKNOWN:
            return UNKNOWN
        if len(candidates) == 1:
            return candidates[0][1]
        if start is not None:
            holding = [c for c in candidates if intervals_overlap(c[0].start, c[0].end, start, end)]
            if holding:
                return max(holding, key=lambda c: position_order(c[0]))[1]
        places = {place for _, place in candidates}
        if UNKNOWN in places:
            return UNKNOWN
        return places.pop() if len(places) == 1 else None

    def _place_of(self, position: Position) -> Place | _Unknown | None:
        """The place a position gives, None if it doesn't count, UNKNOWN if the user can't see where it is"""
        location = self.locations.get(position.location_id)
        if location is None or not location.readable:
            return UNKNOWN
        location_id = self._typed_location(location)
        if location_id is None:
            return None
        if not self.axes:
            return Place(location_id=location_id)
        if position.layout_id is None:
            return None
        layout = self.layouts.get(position.layout_id)
        if layout is None or not layout.readable:
            return UNKNOWN
        values, complete = self._axis_values(layout, position.coordinates)
        axes = []
        for axis in self.axes:
            if axis not in values:
                # a value on a layout above one the user can't see would be unknown
                return None if complete else UNKNOWN
            axes.append((axis, *values[axis]))
        return Place(location_id=location_id, axes=tuple(axes))

    def _typed_location(self, location: LocationContext) -> int | None:
        """The nearest location of one of the types, the location itself or one above it"""
        if location.location_id not in self._typed:
            current, found = location, None
            while current is not None:
                if current.readable and current.type_id in self.types:
                    found = current.location_id
                    break
                current = self.locations.get(current.parent_id) if current.parent_id is not None else None
            self._typed[location.location_id] = found
        return self._typed[location.location_id]

    def _axis_values(self, layout: LayoutContext, coordinates: list | None) -> tuple[dict[str, tuple[int, str]], bool]:
        """
        The values of a position on the axes of its layout and of the layouts above it, by axis name, each with the
        layout that has the axis; and whether every layout above could be read
        """
        values: dict[str, tuple[int, str]] = {}

        def add(owner: LayoutContext, coordinates: list | None):
            for axis, value in zip(owner.axes, coordinates or []):
                if value is not None and str(value) != '':
                    values.setdefault(axis, (owner.layout_id, str(value)))

        add(layout, coordinates)
        child = layout
        while child.parent_id is not None:
            parent = self.layouts.get(child.parent_id)
            if parent is None or not parent.readable or child.position is None:
                return values, False
            add(parent, child.position)
            child = parent
        return values, True
