"""
What deprecating ontology entries does to their relationships, and what cancelling it brings back (README, Ontology).

A relationship follows its entries: deprecating an entry deprecates its current relationships, in both directions,
and the commit that removes the entry removes them with it, so the current ontology has no relationship to an entry it
doesn't have. Each relationship deprecated this way is marked with the entries it was deprecated with (its lifecycle's
`deprecated_with`), so that cancelling an entry's deprecation brings back those relationships, and only those, once
neither end is deprecated. A relationship deprecated on its own is left as it is.

A relationship of a kind that defines its source (OntologyRelationshipLabel.defines_source: all but links to children
and terms) is part of what its source is: an entry can't be deprecated while a current entry has one to it, unless both
are deprecated together, and a deprecation can't be cancelled for an entry while one from it is held deprecated by
another entry, unless both are cancelled together. Links to children and terms are dropped with the entry.

A removed entry can be restored: it comes back as a draft, keeping its id, so data that cites it and new data cite the
same entry, with the relationships removed with it whose other end is current or restored with it. It can't be
restored without what defines it. Restored, it is drafted at the current version, so the views of earlier versions no
longer show it, though its lifecycle's audit trail keeps its history.

The lifecycles given are changed in place; nothing is changed when a rule refuses.
"""
from typing import Dict, Iterable, List

from breedgraph.custom_exceptions import IllegalOperationError
from breedgraph.domain.model.ontology.enums import LifecyclePhase, OntologyEntryLabel
from breedgraph.domain.model.ontology.lifecycle import BaseLifecycle, EntryLifecycle, RelationshipLifecycle
from breedgraph.domain.model.ontology.relationships import OntologyRelationshipBase
from breedgraph.domain.model.ontology.version import Version

# relationships named in a refusal, the rest counted
NAMED = 5


def is_current(lifecycle: BaseLifecycle) -> bool:
    return lifecycle.current_phase in (LifecyclePhase.DRAFT, LifecyclePhase.ACTIVE)


def describe(relationships: List[OntologyRelationshipBase]) -> str:
    named = '; '.join(
        # labels read back from the database are strings
        f"{OntologyEntryLabel(r.source_label).value} {r.source_id} --[{r.label.value}]--> "
        f"{OntologyEntryLabel(r.target_label).value} {r.target_id}"
        for r in relationships[:NAMED]
    )
    return named + (f"; and {len(relationships) - NAMED} more" if len(relationships) > NAMED else '')


def deprecate_with_entries(
        entry_ids: Iterable[int],
        relationships: Iterable[OntologyRelationshipBase],
        relationship_lifecycles: Dict[int, RelationshipLifecycle],
        entry_lifecycles: Dict[int, EntryLifecycle],
        version: Version
) -> None:
    """
    Deprecates, at the version, the relationships of the entries being deprecated, marking each with those of its ends.
    Relationships already deprecated with another entry are marked with these too.
    Refused if a current entry, not among those being deprecated, has a defining relationship to one of them.

    relationships: those of the entries that are not removed, with their lifecycles, and the lifecycles of the entries
    at their other ends.
    """
    entry_ids = set(entry_ids)
    relationships = [r for r in relationships if {r.source_id, r.target_id} & entry_ids]
    blocking = [
        r for r in relationships
        if r.label.defines_source and r.target_id in entry_ids and r.source_id not in entry_ids
        and is_current(entry_lifecycles[r.source_id]) and is_current(relationship_lifecycles[r.id])
    ]
    if blocking:
        raise IllegalOperationError(
            f"Entries that current entries are defined by can't be deprecated, unless they are deprecated together: "
            f"{describe(blocking)}"
        )
    for relationship in relationships:
        lifecycle = relationship_lifecycles[relationship.id]
        ends = {relationship.source_id, relationship.target_id} & entry_ids
        if is_current(lifecycle):
            lifecycle.set_version_deprecated(version)
            lifecycle.deprecated_with = sorted(ends)
        elif lifecycle.current_phase is LifecyclePhase.DEPRECATED and lifecycle.deprecated_with:
            lifecycle.deprecated_with = sorted(ends | set(lifecycle.deprecated_with))


def cancel_with_entries(
        entry_ids: Iterable[int],
        relationships: Iterable[OntologyRelationshipBase],
        relationship_lifecycles: Dict[int, RelationshipLifecycle]
) -> None:
    """
    For entries whose deprecation is cancelled: removes them from the marks of the relationships deprecated with them,
    and cancels the deprecation of those left unmarked.
    Refused if a defining relationship from one of them stays deprecated, held by another entry.

    relationships: those of the entries that are deprecated, with their lifecycles.
    """
    entry_ids = set(entry_ids)
    marked = [
        r for r in relationships
        if relationship_lifecycles[r.id].current_phase is LifecyclePhase.DEPRECATED
        and set(relationship_lifecycles[r.id].deprecated_with) & entry_ids
    ]
    held: Dict[int, List[int]] = {
        r.id: [e for e in relationship_lifecycles[r.id].deprecated_with if e not in entry_ids] for r in marked
    }
    blocking = [r for r in marked if held[r.id] and r.label.defines_source and r.source_id in entry_ids]
    if blocking:
        raise IllegalOperationError(
            f"An entry's deprecation can't be cancelled while an entry it is defined by stays deprecated; cancel both: "
            f"{describe(blocking)}"
        )
    for relationship in marked:
        lifecycle = relationship_lifecycles[relationship.id]
        lifecycle.deprecated_with = held[relationship.id]
        if not lifecycle.deprecated_with:
            lifecycle.cancel_deprecation()


def restore_with_entries(
        entry_ids: Iterable[int],
        relationships: Iterable[OntologyRelationshipBase],
        relationship_lifecycles: Dict[int, RelationshipLifecycle],
        entry_lifecycles: Dict[int, EntryLifecycle],
        version: Version
) -> None:
    """
    For removed entries brought back as drafts at the version: brings back, as drafts too, the relationships removed with
    them whose ends are current or restored with them, and clears their marks.
    Refused if a defining relationship from one of them can't come back, its other end staying removed or deprecated.

    relationships: those of the entries, removed ones included, with their lifecycles, and the lifecycles of the
    entries at their other ends.
    """
    entry_ids = set(entry_ids)

    def back(entry_id: int) -> bool:
        return entry_id in entry_ids or is_current(entry_lifecycles[entry_id])

    marked = [
        r for r in relationships
        if relationship_lifecycles[r.id].current_phase is LifecyclePhase.REMOVED
        and set(relationship_lifecycles[r.id].deprecated_with) & entry_ids
    ]
    returning = {r.id for r in marked if back(r.source_id) and back(r.target_id)}
    blocking = [r for r in marked if r.id not in returning and r.label.defines_source and r.source_id in entry_ids]
    if blocking:
        raise IllegalOperationError(
            f"An entry can't be restored without the entries it is defined by; restore them with it: {describe(blocking)}"
        )
    for relationship in marked:
        if relationship.id in returning:
            lifecycle = relationship_lifecycles[relationship.id]
            lifecycle.set_version_drafted(version)
            lifecycle.deprecated_with = []
