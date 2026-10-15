"""
The program queries under the read policy, through GraphQL, on the read-policy scenario
(see tests/breedgraph/integration/views/test_programs_view.py for the view underneath).
They answer anonymous requests, and placeholders resolve with empty contacts, references and groupings.
"""
import pytest

from breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus

from tests.breedgraph.e2e.utils import post_as, get_verified_payload, assert_payload_success
from tests.breedgraph.scenarios.read_policy_scenario import VIEWERS, PROGRAMS

REDACTED = 'REDACTED'

STUDY_FIELDS = "id name description groupings { id } design { id } licence { id } references { id }"
TRIAL_FIELDS = f"id name description contacts {{ id }} references {{ id }} studies {{ {STUDY_FIELDS} }}"
PROGRAM_FIELDS = f"id name description contacts {{ id }} references {{ id }} trials {{ {TRIAL_FIELDS} }}"


async def post_query(client, login_token_factory, read_policy, viewer: str, query: str, variables: dict | None = None):
    return await post_as(client, login_token_factory, read_policy.user(viewer), query, variables)


def assert_placeholder(entity: dict, *empty_lists: str):
    assert entity['name'] == REDACTED
    assert entity['description'] is None
    for field in empty_lists:
        assert not entity[field], f"placeholder {entity['id']} has {field}: {entity[field]}"


def assert_study(read_policy, viewer: str, name: str, study: dict):
    assert int(study['id']) == read_policy[name]
    if read_policy.readable(viewer, name):
        assert study['name'] != REDACTED
        assert study['groupings']
    else:
        assert_placeholder(study, 'groupings', 'references')
        assert study['design'] is None
        assert study['licence'] is None


def assert_trial(read_policy, viewer: str, name: str, studies: list[str], trial: dict):
    assert int(trial['id']) == read_policy[name]
    if read_policy.readable(viewer, name):
        assert trial['name'] != REDACTED
    else:
        assert_placeholder(trial, 'contacts', 'references')
    by_id = {int(study['id']): study for study in trial['studies']}
    assert set(by_id) == {read_policy[study] for study in studies}, f"{viewer}: studies of {name}"
    for study in studies:
        assert_study(read_policy, viewer, study, by_id[read_policy[study]])


def assert_program(read_policy, viewer: str, name: str, trials: dict[str, list[str]], program: dict):
    assert int(program['id']) == read_policy[name]
    if read_policy.readable(viewer, name):
        assert program['name'] != REDACTED
    else:
        assert_placeholder(program, 'contacts', 'references')
    by_id = {int(trial['id']): trial for trial in program['trials']}
    assert set(by_id) == {read_policy[trial] for trial in trials}, f"{viewer}: trials of {name}"
    for trial, studies in trials.items():
        assert_trial(read_policy, viewer, trial, studies, by_id[read_policy[trial]])


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_programs(client, login_token_factory, read_policy, viewer):
    query = f"query {{ programs {{ status result {{ {PROGRAM_FIELDS} }} errors {{ name message }} }} }}"
    response = await post_query(client, login_token_factory, read_policy, viewer, query)
    payload = get_verified_payload(response, 'programs')
    assert_payload_success(payload)
    expected = read_policy.shown_programs(viewer)
    programs = {int(program['id']): program for program in payload['result']}
    assert set(programs) == {read_policy[name] for name in expected}
    for name, trials in expected.items():
        assert_program(read_policy, viewer, name, trials, programs[read_policy[name]])


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_program_by_id(client, login_token_factory, read_policy, viewer):
    query = (
        "query ($id: ID, $trialId: ID, $studyId: ID) { "
        "  programsProgram(id: $id, trialId: $trialId, studyId: $studyId) { "
        f"   status result {{ {PROGRAM_FIELDS} }} errors {{ name message }} "
        "  } "
        "}"
    )
    expected = read_policy.shown_programs(viewer)
    for name, trials in PROGRAMS.items():
        for variables in (
                {'id': read_policy[name]},
                *({'trialId': read_policy[trial]} for trial in trials),
                *({'studyId': read_policy[study]} for studies in trials.values() for study in studies)
        ):
            response = await post_query(client, login_token_factory, read_policy, viewer, query, variables)
            payload = get_verified_payload(response, 'programsProgram')
            assert_payload_success(payload)
            assert_program(read_policy, viewer, name, expected.get(name, {}), payload['result'])


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_trial_by_id(client, login_token_factory, read_policy, viewer):
    query = (
        "query ($id: ID, $studyId: ID) { "
        "  programsTrial(id: $id, studyId: $studyId) { "
        f"   status result {{ {TRIAL_FIELDS} }} errors {{ name message }} "
        "  } "
        "}"
    )
    for trials in PROGRAMS.values():
        for name, studies in trials.items():
            shown_studies = [study for study in studies if read_policy.readable(viewer, study)]
            for variables in ({'id': read_policy[name]}, *({'studyId': read_policy[study]} for study in studies)):
                response = await post_query(client, login_token_factory, read_policy, viewer, query, variables)
                payload = get_verified_payload(response, 'programsTrial')
                assert_payload_success(payload)
                assert_trial(read_policy, viewer, name, shown_studies, payload['result'])


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_study_by_id(client, login_token_factory, read_policy, viewer):
    query = f"query ($id: ID!) {{ programsStudy(id: $id) {{ status result {{ {STUDY_FIELDS} }} errors {{ name message }} }} }}"
    for trials in PROGRAMS.values():
        for studies in trials.values():
            for name in studies:
                response = await post_query(client, login_token_factory, read_policy, viewer, query, {'id': read_policy[name]})
                payload = get_verified_payload(response, 'programsStudy')
                assert_payload_success(payload)
                assert_study(read_policy, viewer, name, payload['result'])


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', ('admin', 'anonymous'))
async def test_missing_ids_are_not_found(client, login_token_factory, read_policy, viewer):
    missing = max(read_policy.ids.values()) + 1000
    for operation, query in (
            ('programsProgram', "query ($id: ID) { programsProgram(id: $id) { status result { id } errors { name } } }"),
            ('programsTrial', "query ($id: ID) { programsTrial(id: $id) { status result { id } errors { name } } }"),
            ('programsStudy', "query ($id: ID!) { programsStudy(id: $id) { status result { id } errors { name } } }"),
    ):
        response = await post_query(client, login_token_factory, read_policy, viewer, query, {'id': missing})
        payload = get_verified_payload(response, operation)
        assert payload['status'] != GQLStatus.SUCCESS.name
        assert payload['result'] is None
        assert [error['name'] for error in payload['errors']] == ['NoResultFoundError']
