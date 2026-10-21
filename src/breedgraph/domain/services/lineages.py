"""
What comes down a unit graph (README, Unit graph): a factor record describes the units below the one it is on, and a
unit without germplasm of its own takes that of the units above it. Walking up every path of a unit's parents, each path
stops at the first unit with what is sought, so a unit nearer the root doesn't count past a nearer one on the same
lineage; the units found on separate lineages must agree, or none applies (a sample pooled from trees of two
treatments, or of two varieties, takes neither).
"""
from typing import Callable, Hashable, Iterable, TypeVar

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
