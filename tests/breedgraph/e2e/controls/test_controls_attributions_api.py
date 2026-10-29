"""
controlsAttributions, how to credit an entity, through GraphQL, for every viewer of the read-policy scenario,
anonymous included: the attributions of its controlling teams (each its own, or the nearest above it in its team
tree) for an entity the viewer can read, and none for one they can't, nor for an id of no entity. Controller.attributions
gives the same to signed-in viewers.
"""
from collections import defaultdict

import pytest

from breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus

from tests.breedgraph.e2e.utils import post_as, get_verified_payload
from tests.breedgraph.scenarios.read_policy_scenario import VIEWERS, ENTITY_LABELS

QUERY = (
    "query ($label: ControlledModelLabel!, $ids: [ID!]!) { "
    " controlsAttributions(entityLabel: $label, entityIds: $ids) { status result { entityId attributions } errors { name message } } "
    "}"
)
CONTROLLERS = (
    "query ($label: ControlledModelLabel!, $ids: [ID!]!) { "
    " controlsControllers(entityLabel: $label, entityIds: $ids) { status result { attributions } errors { name message } } "
    "}"
)


def _by_label():
    by_label = defaultdict(list)
    for name, label in ENTITY_LABELS.items():
        by_label[label].append(name)
    return by_label


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_attributions(client, login_token_factory, read_policy, viewer):
    for label, names in _by_label().items():
        response = await post_as(
            client, login_token_factory, read_policy.user(viewer), QUERY,
            {'label': label.name, 'ids': [read_policy[name] for name in names]}
        )
        payload = get_verified_payload(response, 'controlsAttributions')
        assert payload['status'] == GQLStatus.SUCCESS.name, payload['errors']
        # one for each id, in the order asked for
        assert [int(item['entityId']) for item in payload['result']] == [read_policy[name] for name in names]
        for name, item in zip(names, payload['result']):
            assert item['attributions'] == read_policy.attributions(viewer, name), f"{viewer}: credit for {name}"


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', [viewer for viewer in VIEWERS if viewer != 'anonymous'])
async def test_controller_attributions(client, login_token_factory, read_policy, viewer):
    for label, names in _by_label().items():
        response = await post_as(
            client, login_token_factory, read_policy.user(viewer), CONTROLLERS,
            {'label': label.name, 'ids': [read_policy[name] for name in names]}
        )
        payload = get_verified_payload(response, 'controlsControllers')
        assert payload['status'] == GQLStatus.SUCCESS.name, payload['errors']
        for name, controller in zip(names, payload['result']):
            assert controller['attributions'] == read_policy.attributions(viewer, name), f"{viewer}: credit for {name}"


@pytest.mark.asyncio(loop_scope="session")
async def test_an_id_of_no_entity_has_none(client, login_token_factory, read_policy):
    missing = max(read_policy.ids.values()) + 1000
    response = await post_as(
        client, login_token_factory, None, QUERY,
        {'label': ENTITY_LABELS['country'].name, 'ids': [missing, read_policy['country']]}
    )
    payload = get_verified_payload(response, 'controlsAttributions')
    assert payload['status'] == GQLStatus.SUCCESS.name, payload['errors']
    assert [(int(item['entityId']), item['attributions']) for item in payload['result']] == [
        (missing, []), (read_policy['country'], read_policy.attributions('anonymous', 'country'))
    ]
    assert payload['result'][1]['attributions'], "the public country is credited to anyone"
