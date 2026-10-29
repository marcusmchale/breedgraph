"""
What comes down a unit graph (README, Unit graph): a factor record describes the units below the one it is on, and a
unit without germplasm of its own takes that of the units above it. Walking up every path of a unit's parents, each path
stops at the first unit with what is sought, so a unit nearer the root doesn't count past a nearer one on the same
lineage; the units found on separate lineages must agree, or none applies (a sample pooled from trees of two
treatments, or of two varieties, takes neither).
"""
from typing import Any, Callable, Hashable, Iterable, TypeVar

V = TypeVar('V', bound=Hashable)


def nearest_on_each_lineage(
        unit_id: int,
        parents_of: Callable[[int], Iterable[int]],
        has: Callable[[int], bool]
) -> list[int]:
    """
    The units nearest above unit_id for which has() holds, the first on each path up its parents, by distance and then
    id; unit_id itself is not among them
    """
    found: list[int] = []
    seen = {unit_id}
    frontier = [unit_id]
    while frontier:
        level, following = [], []
        for current in frontier:
            for parent in parents_of(current):
                if parent in seen:
                    continue
                seen.add(parent)
                (level if has(parent) else following).append(parent)
        found.extend(sorted(level))
        frontier = following
    return found


def lineage_value(
        unit_id: int,
        parents_of: Callable[[int], Iterable[int]],
        value_of: Callable[[int], V | None]
) -> tuple[V | None, int | None]:
    """
    What comes down to a unit: its own value, else the value the nearest units with one agree on, one on each lineage,
    with the nearest of them (by distance, then id); (None, None) when there is none or they differ
    """
    own = value_of(unit_id)
    if own is not None:
        return own, unit_id
    sources = nearest_on_each_lineage(unit_id, parents_of, lambda u: value_of(u) is not None)
    values = {value_of(source) for source in sources}
    if len(values) != 1:
        return None, None
    return values.pop(), sources[0]


# germplasm on a unit the user cannot read: where a lineage stops, unknown
HIDDEN = object()


def germplasm_seen(unit_graph: Any, redacted: Any) -> Callable[[int], Any]:
    """
    A unit's germplasm as the user sees it, for lineage_value: HIDDEN where it has some the user cannot read. The unit
    graph is whole, and redacted is the user's copy of it (UnitGraph.redacted)
    """
    def germplasm_of(unit_id: int):
        germplasm = unit_graph.get_unit(unit_id).germplasm
        if germplasm is None:
            return None
        seen = redacted.get_unit(unit_id).germplasm if redacted.has_unit(unit_id) else None
        return germplasm if seen == germplasm else HIDDEN
    return germplasm_of


def seen_germplasm(unit_graph: Any, redacted: Any, unit_id: int) -> int | None:
    """
    The germplasm of a unit, its own or the one the nearest units above it agree on, as the user sees it: none where
    a lineage stops at a unit whose germplasm is hidden (Unit.inheritedGermplasm)
    """
    germplasm, _ = lineage_value(unit_id, unit_graph.get_parent_ids, germplasm_seen(unit_graph, redacted))
    return None if germplasm is HIDDEN else germplasm


def nearest_unit_of_subjects(unit_id: int, units: dict, subject_ids: set[int]) -> int | None:
    """
    The nearest unit of one of the subjects, the unit itself or an ancestor, when it is below every other one; None when
    there is none, or when they lie on separate lineages (a sample taken from the trees of two plots). units maps a unit
    id to its context, with its subject_id and its ancestor_ids, closest first: a unit missing from it, hidden from the
    user, never counts. The observation unit (grouping.unit) and units of a subject as levels both use it.
    """
    unit = units.get(unit_id)
    if unit is None:
        return None
    candidates = [
        candidate for candidate in [unit_id, *unit.ancestor_ids]
        if candidate in units and units[candidate].subject_id in subject_ids
    ]
    if not candidates:
        return None
    # ancestors are sorted closest first, so the first candidate is the nearest, or one of the nearest
    nearest, *others = candidates
    above = set(units[nearest].ancestor_ids)
    return nearest if all(other in above for other in others) else None
