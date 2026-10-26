"""
What writing positions does to the positions units have, planned here from them as stored, for UnitPositionsService to
write outside the unit graph aggregate (README, Position). Positions have no identity: a position is its value, times
compared as entered (same_position). Each one read for a write keeps the key of the node it is stored as, so that the
write finds it again in the same transaction.

- A move of units to a position from a start ends each unit's own positions holding then at that start (unless they
  end by then), and adds the position. A unit with a position from that start or later is refused, as its history
  would be out of order. Placing units moves each to a position of its own, all or none, and leaves a unit already
  at its place then where it is.
- A change finds one position of each unit by the fields given and replaces the fields given.
- Adding a position refuses one the unit has; removing one refuses a unit graph root's last, as roots are found by
  their positions.

Where a unit is at a time (place_at) is found as the Units pages show it, e.g. for children placed where their parents
were when they were taken.
"""
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Dict, Iterable, List

from numpy import datetime64

from breedgraph.custom_exceptions import IllegalOperationError, NoResultFoundError
from breedgraph.domain.model.time_descriptors import upper, same_time, local_datetime64
from breedgraph.domain.model.unit_graphs import Position, same_position
from breedgraph.domain.services.analysis_places import position_order
from breedgraph.domain.services.lineages import lineage_value, HIDDEN

POSITION_FIELDS = ('location_id', 'layout_id', 'coordinates', 'start', 'end')
PLACE_FIELDS = ('location_id', 'layout_id', 'coordinates')
# units named in a refusal, the rest counted
NAMED = 5


@dataclass
class StoredPosition:
    """A unit's position as read for a write, with the key of the node it is stored as, in this transaction only"""
    key: str
    position: Position


@dataclass
class UnitPositions:
    """A unit's own positions as read for a write"""
    unit_id: int
    name: str | None = None
    root: bool = False
    positions: List[StoredPosition] = field(default_factory=list)


@dataclass
class PositionWrites:
    """The positions to create (unit id and position), to change (node key and what it becomes) and to delete"""
    created: List[tuple[int, Position]] = field(default_factory=list)
    changed: List[tuple[str, Position]] = field(default_factory=list)
    deleted: List[str] = field(default_factory=list)


def validate_position(position: Position) -> None:
    if not position.location_id:
        raise ValueError("Positions require location_id")
    if position.start is not None and position.end is not None and position.start >= upper(position.end):
        raise ValueError("Start cannot be after end")


def holds_at(position: Position, time: datetime64) -> bool:
    """Whether the position holds at the start of the time's period: from its start's period to the end of its end's"""
    return (position.start is None or position.start <= time) and (position.end is None or time < upper(position.end))


def place_at(
        unit_id: int,
        time: datetime64,
        positions_of: Callable[[int], List[Position]],
        parents_of: Callable[[int], Iterable[int]],
        hidden: Callable[[int], bool]
) -> Position | None:
    """
    Where a unit is at a time (README, Position): its own position holding then, the later-starting one after a move,
    else the place the nearest units above it with one then agree on, one on each lineage. A unit the user can't read
    that has positions stops the walk, as in analysis (docs/analysis.md §3), since a place from further up could be
    wrong. Only the place is given: the location, layout and coordinates. None when there is no place then, the
    lineages differ, or a hidden unit stops the walk.
    """
    def holding(unit: int) -> Position | None:
        found = [position for position in positions_of(unit) if holds_at(position, time)]
        return max(found, key=position_order) if found else None

    def place_of(unit: int):
        if hidden(unit):
            return HIDDEN if positions_of(unit) else None
        position = holding(unit)
        if position is None:
            return None
        return position.location_id, position.layout_id, tuple(str(c) for c in position.coordinates or [])

    place, source = lineage_value(unit_id, parents_of, place_of)
    if place is None or place is HIDDEN:
        return None
    position = holding(source)
    return Position(
        location_id=position.location_id,
        layout_id=position.layout_id,
        coordinates=list(position.coordinates) if position.coordinates else None
    )


def matches(position: Position, at: Dict[str, Any]) -> bool:
    """Whether the position has the values given, as entered: times with their precision, coordinates as strings"""
    for name, value in at.items():
        if name in ('start', 'end'):
            given = None if value is None else local_datetime64(value)
            if not same_time(getattr(position, name), given):
                return False
        elif name == 'coordinates':
            if [str(c) for c in position.coordinates or []] != [str(c) for c in value or []]:
                return False
        elif getattr(position, name) != value:
            return False
    return True


def by_name(units: Iterable[UnitPositions]) -> List[UnitPositions]:
    """In the order units are listed: by name, then id"""
    return sorted(units, key=lambda unit: (unit.name is None, (unit.name or '').casefold(), unit.unit_id))


def named(units: List[UnitPositions]) -> str:
    """Some of these units by name, the rest counted"""
    names = [unit.name or f"unit {unit.unit_id}" for unit in by_name(units)[:NAMED]]
    if len(units) > NAMED:
        return f"{', '.join(names)} and {len(units) - NAMED} more"
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


def _check_fields(fields: Dict[str, Any]) -> None:
    unknown = set(fields) - set(POSITION_FIELDS)
    if unknown:
        raise ValueError(f"Positions have no {', '.join(sorted(unknown))}")


def _move(unit: UnitPositions, position: Position, writes: PositionWrites) -> bool:
    """
    The unit to the position from its start, into writes: its own positions holding then end at that start, so both
    hold during it (the unit is where the later-starting one puts it), and the position is added. False, writing
    nothing, when the unit has a position from that start or later
    """
    start = position.start
    if any(stored.position.start is not None and stored.position.start >= start for stored in unit.positions):
        return False
    for stored in unit.positions:
        # one ending then already, or ending in a period that holds the start, keeps its end as entered
        if holds_at(stored.position, start) and (stored.position.end is None or stored.position.end > start):
            writes.changed.append((stored.key, replace(stored.position, end=start)))
    writes.created.append((unit.unit_id, position))
    return True


def _check_move(position: Position) -> None:
    if position.start is None:
        raise ValueError("A move needs a start: when the units arrive")
    validate_position(position)


def plan_move(units: Iterable[UnitPositions], position: Position) -> PositionWrites:
    """Each unit to the position from its start (_move)"""
    _check_move(position)
    writes = PositionWrites()
    later = [unit for unit in units if not _move(unit, position, writes)]
    if later:
        raise IllegalOperationError(
            f"{named(later)} {'has a position' if len(later) == 1 else 'have positions'} from {position.start} or "
            f"later, so can't be moved then: move them from a later time, or correct those positions"
        )
    return writes


def _place(position: Position):
    return position.location_id, position.layout_id, tuple(str(c) for c in position.coordinates or [])


def plan_place(placements: Iterable[tuple[UnitPositions, Position]]) -> PositionWrites:
    """
    Each unit to a position of its own from its start (_move), all or none. A unit whose own position holding then is
    at the same place already stays as it is, so placing units again where they are changes nothing
    """
    writes = PositionWrites()
    later = []
    for unit, position in placements:
        _check_move(position)
        if any(
                holds_at(stored.position, position.start) and _place(stored.position) == _place(position)
                for stored in unit.positions
        ):
            continue
        if not _move(unit, position, writes):
            later.append(unit)
    if later:
        raise IllegalOperationError(
            f"{named(later)} {'has a position' if len(later) == 1 else 'have positions'} from when "
            f"{'it is' if len(later) == 1 else 'they are'} placed or later, so can't be placed then: place "
            f"{'it' if len(later) == 1 else 'them'} from a later time, or correct those positions"
        )
    return writes


def plan_change(units: Iterable[UnitPositions], at: Dict[str, Any], change: Dict[str, Any]) -> PositionWrites:
    """
    One position of each unit, found by the values in at (as entered; those not given match any), given the values
    in change (those not given are kept)
    """
    _check_fields(at)
    _check_fields(change)
    if not change:
        raise ValueError("Give what changes")
    if 'location_id' in change and change['location_id'] is None:
        raise ValueError("Positions require location_id")
    writes = PositionWrites()
    missing, several, duplicated = [], [], []
    for unit in units:
        found = [stored for stored in unit.positions if matches(stored.position, at)]
        if not found:
            missing.append(unit)
            continue
        if len(found) > 1:
            several.append(unit)
            continue
        stored, = found
        changed = replace(stored.position, **change)
        validate_position(changed)
        if any(same_position(changed, other.position) for other in unit.positions if other is not stored):
            duplicated.append(unit)
            continue
        writes.changed.append((stored.key, changed))
    if missing:
        raise NoResultFoundError(f"No position matching the details given was found for {named(missing)}, nothing changed")
    if several:
        raise ValueError(
            f"Several positions match the details given for {named(several)}: give more of them, e.g. the start"
        )
    if duplicated:
        raise ValueError(f"{named(duplicated)} would have the same position twice, nothing changed")
    return writes


def plan_add(unit: UnitPositions, position: Position) -> PositionWrites:
    validate_position(position)
    if any(same_position(position, stored.position) for stored in unit.positions):
        raise ValueError("The unit already has this position")
    return PositionWrites(created=[(unit.unit_id, position)])


def plan_remove(unit: UnitPositions, position: Position) -> PositionWrites:
    found = next((stored for stored in unit.positions if same_position(position, stored.position)), None)
    if found is None:
        raise ValueError("A position matching the provided details was not found, nothing changed")
    if unit.root and len(unit.positions) == 1:
        raise IllegalOperationError("Unit graph root units must have at least one position defined to support discovery")
    return PositionWrites(deleted=[found.key])
