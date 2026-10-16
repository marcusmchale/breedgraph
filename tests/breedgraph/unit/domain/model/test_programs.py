import pytest
from numpy import datetime64

from breedgraph.domain.model.controls import Controller, Control, ReadRelease
from breedgraph.domain.model.programs import (
    ProgramStored, TrialStored, StudyStored, RecordGroupingStored, RecordGroupingInput, GroupingScope
)
from breedgraph.domain.model.ontology import RecordGroupExtent
from breedgraph.service_layer.tracking.wrappers import tracked


@pytest.fixture
def program() -> ProgramStored:
    """A program whose trial, study and grouping all have id 0, as the first of each in a database"""
    grouping = RecordGroupingStored(
        id=0, type=1, name="Replicate", scope=GroupingScope.DATASET_SCOPED, extent=RecordGroupExtent.WITHIN_UNIT
    )
    study = StudyStored(id=0, name="Study", groupings=[grouping])
    trial = TrialStored(id=0, name="Trial", studies={0: study})
    return ProgramStored(id=0, name="Program", trials={0: trial})


def test_get_grouping_by_id_zero(program):
    study = program.get_study(study_id=0)
    assert study.get_grouping(grouping_id=0).name == "Replicate"
    assert study.get_grouping(name="replicate").id == 0
    assert study.get_grouping(grouping_id=1) is None


def test_grouping_requires_an_extent():
    with pytest.raises(ValueError, match="A record grouping requires an extent"):
        RecordGroupingInput(type=1, name="Replicate", scope=GroupingScope.STUDY_WIDE)


def test_add_grouping_with_its_extent(program):
    study = program.get_study(study_id=0)
    study.add_grouping(2, "Block", GroupingScope.STUDY_WIDE, RecordGroupExtent.WITHIN_GRAPH)
    assert study.get_grouping(name="Block").extent is RecordGroupExtent.WITHIN_GRAPH


def test_merge_dataset_scope_coalesces_overlapping_scopes():
    grouping = tracked(RecordGroupingStored(
        id=0, type=1, name="Replicate", scope=GroupingScope.DATASET_SCOPED, extent=RecordGroupExtent.WITHIN_UNIT
    ))
    for scope in ([1, 2], [3], [4, 5], [2, 4], [9]):
        grouping.merge_dataset_scope(scope)
    assert [sorted(scope.dataset_ids) for scope in grouping.dataset_scopes] == [[3], [1, 2, 4, 5], [9]]
    assert 'dataset_scopes' in grouping.changed
    # each merge gives the grouping a new list of the scopes kept, which hold a callback to the current list only
    assert len(grouping.dataset_scopes[0]._self_on_changed) == 1


def test_get_trial_by_id_or_study(program):
    assert program.get_trial(trial_id=0).name == "Trial"
    assert program.get_trial(study_id=0).name == "Trial"
    with pytest.raises(ValueError, match="Trial or Study ID required"):
        program.get_trial()


def controlled_program() -> tuple[ProgramStored, dict]:
    """
    A public program with a private trial (1) holding study 10, and a public trial (2) holding a private study (20)
    and a public study (21), all controlled by team 1, with their controllers keyed as the repository gives them
    """
    program = ProgramStored(id=0, name="Program", trials={
        1: TrialStored(id=1, name="Hidden trial", studies={10: StudyStored(id=10, name="Study in hidden trial")}),
        2: TrialStored(id=2, name="Open trial", studies={
            20: StudyStored(id=20, name="Hidden study"),
            21: StudyStored(id=21, name="Open study")
        })
    })
    controller = lambda release: Controller(
        controls={1: Control(user_id=1, team_id=1, release=release, time=datetime64('now'))}
    )
    controllers = {
        'Program': {0: controller(ReadRelease.PUBLIC)},
        'Trial': {1: controller(ReadRelease.PRIVATE), 2: controller(ReadRelease.PUBLIC)},
        'Study': {10: controller(ReadRelease.PUBLIC), 20: controller(ReadRelease.PRIVATE), 21: controller(ReadRelease.PUBLIC)}
    }
    return program, controllers


def test_redaction_removes_hidden_trials_and_studies_for_anonymous_users():
    program, controllers = controlled_program()
    redacted = program.redacted(controllers=controllers, user_id=None, read_teams=None)
    # the hidden trial goes with its studies, readable or not
    assert list(redacted.trials) == [2]
    assert list(redacted.trials[2].studies) == [21]
    assert redacted.trials[2].studies[21].name == "Open study"


def test_redaction_redacts_hidden_trials_and_studies_for_registered_users():
    program, controllers = controlled_program()
    redacted = program.redacted(controllers=controllers, user_id=2, read_teams=set())
    assert redacted.trials[1].name == TrialStored.redacted_str
    # a readable study of a hidden trial is still shown
    assert redacted.trials[1].studies[10].name == "Study in hidden trial"
    assert redacted.trials[2].studies[20].name == StudyStored.redacted_str
    assert redacted.trials[2].studies[21].name == "Open study"


def test_redaction_leaves_everything_for_controlling_teams():
    program, controllers = controlled_program()
    redacted = program.redacted(controllers=controllers, user_id=1, read_teams={1})
    assert [trial.name for trial in redacted.trials.values()] == ["Hidden trial", "Open trial"]
    assert [study.name for study in redacted.trials[2].studies.values()] == ["Hidden study", "Open study"]
