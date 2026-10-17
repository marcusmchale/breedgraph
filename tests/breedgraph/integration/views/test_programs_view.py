"""
Programs under the read policy (docs/read-access.md), on the read-policy scenario:

    program (child, private) > trial (child, private) > study_public (child, public), study_private (child, private)
    program_public (root, public) > trial_public (root, public) > study_registered (root, registered)

A program, trial or study the viewer cannot read is a placeholder where it holds something they can read (rule 4,
fixed depth) or when asked for by id (rule 2), and is otherwise left out (rule 5). A program or trial looked up by a
trial or study is found only from one the viewer can read, or a hidden trial holding a study they can read (rule 5).
"""
import pytest

from breedgraph.domain.model.programs import ProgramStored, TrialStored, StudyStored

from tests.breedgraph.scenarios.read_policy_scenario import VIEWERS, PROGRAMS

REDACTED = 'REDACTED'


def start_shown(read_policy, viewer: str, start: str) -> bool:
    """Whether a program or trial can be looked up from this trial or study: readable, or a trial holding a readable study"""
    if read_policy.readable(viewer, start):
        return True
    studies = next((trials[start] for trials in PROGRAMS.values() if start in trials), [])
    return any(read_policy.readable(viewer, study) for study in studies)


def assert_study(read_policy, viewer: str, name: str, study: StudyStored):
    assert study.id == read_policy[name]
    if read_policy.readable(viewer, name):
        assert study.name != REDACTED
        assert study.groupings, f"{viewer} should see the groupings of {name}"
    else:
        assert study.name == REDACTED
        assert study.groupings == []
        assert study.reference_ids == []
        assert study.description is None


def assert_trial(read_policy, viewer: str, name: str, studies: list[str], trial: TrialStored):
    assert trial.id == read_policy[name]
    if read_policy.readable(viewer, name):
        assert trial.name != REDACTED
    else:
        assert trial.name == REDACTED
        assert trial.contact_ids == []
        assert trial.reference_ids == []
        assert trial.description is None
    assert set(trial.studies) == {read_policy[study] for study in studies}, f"{viewer}: studies of {name}"
    for study in studies:
        assert_study(read_policy, viewer, study, trial.studies[read_policy[study]])


def assert_program(read_policy, viewer: str, name: str, trials: dict[str, list[str]], program: ProgramStored):
    assert program.id == read_policy[name]
    if read_policy.readable(viewer, name):
        assert program.name != REDACTED
    else:
        assert program.name == REDACTED
        assert program.contact_ids == []
        assert program.reference_ids == []
        assert program.description is None
    assert set(program.trials) == {read_policy[trial] for trial in trials}, f"{viewer}: trials of {name}"
    for trial, studies in trials.items():
        assert_trial(read_policy, viewer, trial, studies, program.trials[read_policy[trial]])


def test_expected_shapes(read_policy):
    """The scenario gives each viewer a different shape, so the tests below are not vacuous"""
    assert read_policy.shown_programs('admin') == PROGRAMS
    assert read_policy.shown_programs('outsider') == {
        'program': {'trial': ['study_public']},
        'program_public': {'trial_public': ['study_registered']}
    }
    assert read_policy.shown_programs('anonymous') == {
        'program': {'trial': ['study_public']},
        'program_public': {'trial_public': []}
    }


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_get_programs(views_factory, read_policy, viewer):
    async with views_factory.get_views(user_id=read_policy.user(viewer)) as views:
        programs = {program.id: program for program in await views.programs.get_programs()}
    expected = read_policy.shown_programs(viewer)
    assert set(programs) == {read_policy[name] for name in expected}
    for name, trials in expected.items():
        assert_program(read_policy, viewer, name, trials, programs[read_policy[name]])


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_get_program_by_id(views_factory, read_policy, viewer):
    """Asked for by its id a program is returned even when hidden and holding nothing the viewer can read, and asked
    for by a trial's or study's when that start may be looked up from; its trials and studies follow the same rules
    as in the list"""
    expected = read_policy.shown_programs(viewer)
    async with views_factory.get_views(user_id=read_policy.user(viewer)) as views:
        for name, trials in PROGRAMS.items():
            shown_trials = expected.get(name, {})
            program = await views.programs.get_program(program_id=read_policy[name])
            assert_program(read_policy, viewer, name, shown_trials, program)
            for trial, studies in trials.items():
                by_trial = await views.programs.get_program(trial_id=read_policy[trial])
                if start_shown(read_policy, viewer, trial):
                    assert_program(read_policy, viewer, name, shown_trials, by_trial)
                else:
                    assert by_trial is None, f"{viewer}: program found from {trial}"
                for study in studies:
                    by_study = await views.programs.get_program(study_id=read_policy[study])
                    if start_shown(read_policy, viewer, study):
                        assert_program(read_policy, viewer, name, shown_trials, by_study)
                    else:
                        assert by_study is None, f"{viewer}: program found from {study}"


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_get_trial_by_id(views_factory, read_policy, viewer):
    async with views_factory.get_views(user_id=read_policy.user(viewer)) as views:
        for trials in PROGRAMS.values():
            for name, studies in trials.items():
                shown_studies = [study for study in studies if read_policy.readable(viewer, study)]
                trial = await views.programs.get_trial(trial_id=read_policy[name])
                assert_trial(read_policy, viewer, name, shown_studies, trial)
                for study in studies:
                    by_study = await views.programs.get_trial(study_id=read_policy[study])
                    if start_shown(read_policy, viewer, study):
                        assert_trial(read_policy, viewer, name, shown_studies, by_study)
                    else:
                        assert by_study is None, f"{viewer}: trial found from {study}"


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_get_study_by_id(views_factory, read_policy, viewer):
    async with views_factory.get_views(user_id=read_policy.user(viewer)) as views:
        for trials in PROGRAMS.values():
            for studies in trials.values():
                for name in studies:
                    study = await views.programs.get_study(study_id=read_policy[name])
                    assert_study(read_policy, viewer, name, study)


@pytest.mark.asyncio(loop_scope="session")
async def test_missing_ids_give_none(views_factory, read_policy):
    missing = max(read_policy.ids.values()) + 1000
    async with views_factory.get_views(user_id=read_policy.user('admin')) as views:
        assert await views.programs.get_program(program_id=missing) is None
        assert await views.programs.get_program(study_id=missing) is None
        assert await views.programs.get_trial(trial_id=missing) is None
        assert await views.programs.get_study(study_id=missing) is None
