"""Relationships follow their entries' lifecycle (domain.services.ontology_lifecycles)"""
import pytest

from breedgraph.custom_exceptions import IllegalOperationError
from breedgraph.domain.model.ontology import (
    OntologyEntryLabel, LifecyclePhase, Version, EntryLifecycle, RelationshipLifecycle,
    ParentRelationship, TermRelationship, SubjectRelationship, CategoryRelationship, VariableComponentRelationship
)
from breedgraph.domain.model.ontology.relationships import VariableScaleRelationship
from breedgraph.domain.services.ontology_lifecycles import deprecate_with_entries, cancel_with_entries, restore_with_entries

V1, V2, V3, V4 = Version(major=1), Version(major=2), Version(major=3), Version(major=4)

# variables 1 and 8 use scale 2, which has category 3; variable 1 describes trait 4 and has term 6;
# trait 4 describes subject 5, the parent of subject 7
VARIABLE, SCALE, CATEGORY, TRAIT, SUBJECT, TERM, CHILD_SUBJECT, OTHER_VARIABLE = 1, 2, 3, 4, 5, 6, 7, 8
RELATIONSHIPS = {
    101: VariableScaleRelationship.build(variable_id=VARIABLE, scale_id=SCALE),
    102: CategoryRelationship.build(scale_id=SCALE, category_id=CATEGORY),
    103: VariableComponentRelationship.TraitRelationship.build(variable_id=VARIABLE, trait_id=TRAIT),
    104: SubjectRelationship.build(source_id=TRAIT, subject_id=SUBJECT, source_label=OntologyEntryLabel.TRAIT),
    105: TermRelationship.build(source_id=VARIABLE, term_id=TERM, source_label=OntologyEntryLabel.VARIABLE),
    106: ParentRelationship.build(
        parent_id=SUBJECT, child_id=CHILD_SUBJECT, source_label=OntologyEntryLabel.SUBJECT, target_label=OntologyEntryLabel.SUBJECT
    ),
    107: VariableScaleRelationship.build(variable_id=OTHER_VARIABLE, scale_id=SCALE),
}
for relationship_id, relationship in RELATIONSHIPS.items():
    relationship.id = relationship_id


@pytest.fixture
def lifecycles():
    entries = {
        entry_id: EntryLifecycle(entry_id=entry_id, drafted=V1, activated=V1)
        for entry_id in (VARIABLE, SCALE, CATEGORY, TRAIT, SUBJECT, TERM, CHILD_SUBJECT, OTHER_VARIABLE)
    }
    relationships = {
        relationship_id: RelationshipLifecycle(relationship_id=relationship_id, drafted=V1, activated=V1)
        for relationship_id in RELATIONSHIPS
    }
    return entries, relationships


def deprecate(entry_ids, lifecycles, version=V2):
    entries, relationships = lifecycles
    deprecate_with_entries(entry_ids, RELATIONSHIPS.values(), relationships, entries, version)
    # as the service then does
    for entry_id in entry_ids:
        if entries[entry_id].current_phase is not LifecyclePhase.DEPRECATED:
            entries[entry_id].set_version_deprecated(version)


def cancel(entry_ids, lifecycles):
    entries, relationships = lifecycles
    cancel_with_entries(entry_ids, RELATIONSHIPS.values(), relationships)
    for entry_id in entry_ids:
        entries[entry_id].cancel_deprecation()


def commit(lifecycles, version=V3):
    """As a commit does: what is deprecated is removed"""
    entries, relationships = lifecycles
    for lifecycle in [*entries.values(), *relationships.values()]:
        if lifecycle.current_phase is LifecyclePhase.DEPRECATED:
            lifecycle.set_version_removed(version)


def restore(entry_ids, lifecycles, version=V3):
    entries, relationships = lifecycles
    restore_with_entries(entry_ids, RELATIONSHIPS.values(), relationships, entries, version)
    for entry_id in entry_ids:
        entries[entry_id].set_version_drafted(version)


def removed(lifecycles) -> dict[int, list[int]]:
    """The removed relationships, with the entries they were deprecated with"""
    _, relationships = lifecycles
    return {
        relationship_id: lifecycle.deprecated_with for relationship_id, lifecycle in relationships.items()
        if lifecycle.current_phase is LifecyclePhase.REMOVED
    }


def marks(lifecycles) -> dict[int, list[int]]:
    """The deprecated relationships, with the entries they were deprecated with"""
    _, relationships = lifecycles
    return {
        relationship_id: lifecycle.deprecated_with for relationship_id, lifecycle in relationships.items()
        if lifecycle.current_phase is LifecyclePhase.DEPRECATED
    }


def test_an_entry_takes_its_relationships_with_it_in_both_directions(lifecycles):
    deprecate([VARIABLE], lifecycles)
    assert marks(lifecycles) == {101: [VARIABLE], 103: [VARIABLE], 105: [VARIABLE]}
    assert lifecycles[1][101].deprecated == V2


def test_an_entry_a_current_entry_is_defined_by_is_kept(lifecycles):
    with pytest.raises(IllegalOperationError, match="Variable 1 --\\[UsesScale\\]--> Scale 2; Variable 8"):
        deprecate([SCALE], lifecycles)
    assert marks(lifecycles) == {}, "nothing changed"
    # a trait's subjects define it too
    with pytest.raises(IllegalOperationError, match="Trait 4 --\\[DescribesSubject\\]--> Subject 5"):
        deprecate([SUBJECT], lifecycles)


def test_entries_deprecated_together_mark_what_they_share(lifecycles):
    deprecate([VARIABLE, OTHER_VARIABLE, SCALE], lifecycles)
    assert marks(lifecycles) == {
        101: [VARIABLE, SCALE], 102: [SCALE], 103: [VARIABLE], 105: [VARIABLE], 107: [SCALE, OTHER_VARIABLE]
    }


def test_a_term_is_dropped_but_not_a_trait(lifecycles):
    deprecate([TERM], lifecycles)
    assert marks(lifecycles) == {105: [TERM]}, "the variable stays current without its term"
    with pytest.raises(IllegalOperationError, match="Variable 1 --\\[DescribesTrait\\]--> Trait 4"):
        deprecate([TRAIT, SUBJECT], lifecycles)


def test_a_child_subject_stays_current_without_its_parent(lifecycles):
    deprecate([VARIABLE, TRAIT, SUBJECT], lifecycles)
    assert marks(lifecycles)[106] == [SUBJECT]
    assert lifecycles[0][CHILD_SUBJECT].current_phase is LifecyclePhase.ACTIVE


def test_a_relationship_deprecated_on_its_own_is_left_alone(lifecycles):
    _, relationships = lifecycles
    relationships[105].set_version_deprecated(V1)
    deprecate([VARIABLE], lifecycles)
    assert marks(lifecycles)[105] == []
    assert relationships[105].deprecated == V1
    cancel([VARIABLE], lifecycles)
    assert marks(lifecycles) == {105: []}, "only what was deprecated with the variable comes back"


def test_a_later_deprecation_adds_to_the_marks(lifecycles):
    deprecate([VARIABLE], lifecycles)
    deprecate([OTHER_VARIABLE, SCALE], lifecycles, version=V3)
    assert marks(lifecycles)[101] == [VARIABLE, SCALE]
    assert lifecycles[1][101].deprecated == V2, "deprecated when the variable was"


def test_cancelling_brings_back_what_is_no_longer_held(lifecycles):
    deprecate([VARIABLE, OTHER_VARIABLE, SCALE], lifecycles)
    cancel([SCALE], lifecycles)
    # the scale's category comes back, and its link to the variables stays with them
    assert marks(lifecycles) == {101: [VARIABLE], 103: [VARIABLE], 105: [VARIABLE], 107: [OTHER_VARIABLE]}
    cancel([VARIABLE, OTHER_VARIABLE], lifecycles)
    assert marks(lifecycles) == {}
    assert lifecycles[1][101].current_phase is LifecyclePhase.ACTIVE


def test_an_entry_comes_back_only_with_what_defines_it(lifecycles):
    deprecate([VARIABLE, OTHER_VARIABLE, SCALE], lifecycles)
    with pytest.raises(IllegalOperationError, match="cancel both: Variable 1 --\\[UsesScale\\]--> Scale 2"):
        cancel([VARIABLE], lifecycles)
    assert marks(lifecycles)[101] == [VARIABLE, SCALE], "nothing changed"
    cancel([VARIABLE, SCALE], lifecycles)
    assert marks(lifecycles) == {107: [OTHER_VARIABLE]}


def test_a_removed_entry_comes_back_only_with_what_defines_it(lifecycles):
    deprecate([VARIABLE, OTHER_VARIABLE, SCALE], lifecycles)
    commit(lifecycles)
    with pytest.raises(IllegalOperationError, match="restore them with it: Variable 1 --\\[UsesScale\\]--> Scale 2"):
        restore([VARIABLE], lifecycles)
    assert set(removed(lifecycles)) == {101, 102, 103, 105, 107}, "nothing changed"
    restore([VARIABLE, SCALE], lifecycles)
    # the other variable stays removed, with its link to the scale
    assert removed(lifecycles) == {107: [SCALE, OTHER_VARIABLE]}
    entries, relationships = lifecycles
    assert relationships[101].current_phase is LifecyclePhase.DRAFT and relationships[101].deprecated_with == []
    assert relationships[101].drafted == V3


def test_a_restored_scale_leaves_its_removed_variables(lifecycles):
    deprecate([VARIABLE, OTHER_VARIABLE, SCALE], lifecycles)
    commit(lifecycles)
    restore([SCALE], lifecycles)
    assert set(removed(lifecycles)) == {101, 103, 105, 107}, "only its category comes back"


def test_what_was_removed_since_stays_removed(lifecycles):
    deprecate([VARIABLE], lifecycles)
    commit(lifecycles)
    deprecate([TERM], lifecycles, version=V3)
    commit(lifecycles, version=V4)
    restore([VARIABLE], lifecycles, version=V4)
    # the term is removed, and links to terms don't define the variable, so it comes back without it
    assert removed(lifecycles) == {105: [VARIABLE]}
