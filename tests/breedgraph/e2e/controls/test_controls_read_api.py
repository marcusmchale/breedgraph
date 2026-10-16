"""
controlsControllers under the read policy, through GraphQL, for every entity of the read-policy scenario
(see tests/breedgraph/integration/views/test_controls_view.py for the view underneath).

Signed-in users only: anonymous requests are refused. For each entity:
- access: what the viewer's affiliations let them do through the controlling teams, READ following the release;
- teams and each control's team: hidden teams stood in for by the nearest team the viewer can see (rule 7);
- writes, writeCount, created, updated and control times: only where the viewer can read the entity;
- a write's person: the writer's Person, a placeholder if hidden, null if the account has none.
"""
from collections import defaultdict

import pytest

from breedgraph.domain.model.controls import Access
from breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus

from tests.breedgraph.e2e.utils import post_as, get_verified_payload
from tests.breedgraph.scenarios.read_policy_scenario import VIEWERS, ENTITY_LABELS, AFFILIATIONS, PEOPLE

CONTROLLER_FIELDS = (
    "access release writeCount created updated "
    "teams { team { id } standIn } "
    "controls { team { team { id } standIn } release time } "
    "writes { time person { id restricted } }"
)
QUERY = (
    "query ($label: ControlledModelLabel!, $ids: [ID!]!) { "
    f" controlsControllers(entityLabel: $label, entityIds: $ids) {{ status result {{ {CONTROLLER_FIELDS} }} errors {{ name message }} }} "
    "}"
)
WRITERS = {'root': 'admin', 'child': 'writer', 'other': 'stranger'}
# a team other than a team tree's root is visible only to its affiliates; the root stands in for it
STAND_INS = {'child': 'root'}


def team_reference(read_policy, viewer: str, team: str) -> tuple[int, bool]:
    if team in STAND_INS and team not in AFFILIATIONS.get(viewer, {}):
        return read_policy[STAND_INS[team]], True
    return read_policy[team], False


def expected_access(read_policy, viewer: str, name: str) -> set[str]:
    team, _ = read_policy.controls[name]
    access = {a for a in AFFILIATIONS[viewer].get(team, set()) if a is not Access.READ}
    if read_policy.readable(viewer, name):
        access.add(Access.READ)
    return {a.name for a in access}


def writer_person(read_policy, viewer: str, name: str) -> tuple[int, bool] | None:
    """The first writer's Person as (id, restricted), None if the writer has no Person"""
    team, _ = read_policy.controls[name]
    linked = [person for person, (_, _, _, user, _) in PEOPLE.items() if user == WRITERS[team]]
    if not linked:
        return None
    person = linked[0]
    shown = read_policy.readable(viewer, person) or PEOPLE[person][3] == viewer
    return read_policy[person], not shown


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', [viewer for viewer in VIEWERS if viewer != 'anonymous'])
async def test_controllers(client, login_token_factory, read_policy, viewer):
    by_label = defaultdict(list)
    for name, label in ENTITY_LABELS.items():
        by_label[label].append(name)

    for label, names in by_label.items():
        response = await post_as(
            client, login_token_factory, read_policy.user(viewer), QUERY,
            {'label': label.name, 'ids': [read_policy[name] for name in names]}
        )
        payload = get_verified_payload(response, 'controlsControllers')
        assert payload['status'] == GQLStatus.SUCCESS.name, payload['errors']
        # in the order asked for
        for name, controller in zip(names, payload['result']):
            team, release = read_policy.controls[name]
            readable = read_policy.readable(viewer, name)
            assert set(controller['access']) == expected_access(read_policy, viewer, name), f"{viewer}: access to {name}"
            assert controller['release'] == release.name
            assert [(int(reference['team']['id']), reference['standIn']) for reference in controller['teams']] == \
                [team_reference(read_policy, viewer, team)], f"{viewer}: teams of {name}"
            (control,) = controller['controls']
            assert (int(control['team']['team']['id']), control['team']['standIn']) == team_reference(read_policy, viewer, team)
            assert control['release'] == release.name
            if readable:
                assert control['time'] is not None
                assert controller['writeCount'] == len(controller['writes']) > 0
                assert controller['created'] is not None and controller['updated'] is not None
                person = controller['writes'][0]['person']
                expected_person = writer_person(read_policy, viewer, name)
                if expected_person is None:
                    assert person is None, f"{viewer}: the writer of {name} has no Person"
                else:
                    assert (int(person['id']), person['restricted']) == expected_person, f"{viewer}: writer of {name}"
            else:
                assert control['time'] is None
                assert controller['writes'] == []
                assert controller['writeCount'] == 0
                assert controller['created'] is None and controller['updated'] is None


@pytest.mark.asyncio(loop_scope="session")
async def test_anonymous_is_refused(client, login_token_factory, read_policy):
    response = await post_as(
        client, login_token_factory, None, QUERY,
        {'label': ENTITY_LABELS['country'].name, 'ids': [read_policy['country']]}
    )
    payload = get_verified_payload(response, 'controlsControllers')
    assert payload['status'] != GQLStatus.SUCCESS.name
    assert payload['result'] is None
