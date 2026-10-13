import pytest

from breedgraph.domain.model.programs import (
    ProgramStored, TrialStored, StudyStored, RecordGroupingStored, GroupingScope
)


@pytest.fixture
def program() -> ProgramStored:
    """A program whose trial, study and grouping all have id 0, as the first of each in a database"""
    grouping = RecordGroupingStored(id=0, type=1, name="Replicate", scope=GroupingScope.DATASET_SCOPED)
    study = StudyStored(id=0, name="Study", groupings=[grouping])
    trial = TrialStored(id=0, name="Trial", studies={0: study})
    return ProgramStored(id=0, name="Program", trials={0: trial})


def test_get_grouping_by_id_zero(program):
    study = program.get_study(study_id=0)
    assert study.get_grouping(grouping_id=0).name == "Replicate"
    assert study.get_grouping(name="replicate").id == 0
    assert study.get_grouping(grouping_id=1) is None


def test_get_trial_by_id_or_study(program):
    assert program.get_trial(trial_id=0).name == "Trial"
    assert program.get_trial(study_id=0).name == "Trial"
    with pytest.raises(ValueError, match="Trial or Study ID required"):
        program.get_trial()
