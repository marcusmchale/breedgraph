"""
The unit queries under the read policy, through GraphQL, on the read-policy scenario
(see tests/breedgraph/integration/views/test_units_view.py for the view underneath).
They answer anonymous requests; a unit's parents, children, germplasm and positions' locations resolve,
as placeholders where the viewer cannot read them.
"""
import pytest

from breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus

from tests.breedgraph.e2e.utils import post_as, get_verified_payload
from tests.breedgraph.scenarios.read_policy_scenario import VIEWERS, UNIT_PARENTS

REDACTED = 'REDACTED'

UNIT_FIELDS = (
    "id name subject { id } germplasm { id name } positions { location { id name } } "
    "parents { id name } children { id name }"
)
UNIT_LOCATIONS = {'field_unit': 'field', 'tree_public': 'state', 'plot_public': 'field_registered', 'plot_private': 'field'}
UNIT_GERMPLASM = {'tree_public': 'crop_leaf', 'tree_registered': 'crop_middle'}


async def query(client, login_token_factory, read_policy, viewer: str, operation: str, text: str, variables=None):
    response = await post_as(client, login_token_factory, read_policy.user(viewer), text, variables)
    payload = get_verified_payload(response, operation)
    # an empty list is a valid result here, so not assert_payload_success
    assert payload['status'] == GQLStatus.SUCCESS.name, payload['errors']
    assert payload['errors'] is None
    return payload['result']


def assert_linked(read_policy, viewer: str, linked: dict | None, name: str | None):
    """A linked entity, by its name in the scenario, named only where the viewer can read it"""
    if name is None:
        assert linked is None
        return
    assert linked is not None, f"{viewer}: {name} should be linked"
    assert int(linked['id']) == read_policy[name]
    assert (linked['name'] != REDACTED) == read_policy.readable(viewer, name), f"{viewer}: {name} as linked"


def assert_unit(read_policy, viewer: str, name: str, unit: dict):
    expected = read_policy.tree_member(viewer, UNIT_PARENTS, name)
    assert int(unit['id']) == read_policy[name]
    assert (unit['name'] != REDACTED) == expected.readable, f"{viewer}: {name}"
    if expected.readable:
        assert unit['subject'] is not None
        assert_linked(read_policy, viewer, unit['germplasm'], UNIT_GERMPLASM.get(name))
        locations = [position['location'] for position in unit['positions']]
        if name in UNIT_LOCATIONS:
            assert len(locations) == 1
            assert_linked(read_policy, viewer, locations[0], UNIT_LOCATIONS[name])
        else:
            assert locations == []
        parents = unit['parents']
        if expected.parent:
            assert len(parents) == 1
            assert_linked(read_policy, viewer, parents[0], expected.parent)
        else:
            assert parents == []
    else:
        assert unit['subject'] is None
        assert unit['germplasm'] is None
        assert not unit['positions']
        assert not unit['parents']
    children = {int(child['id']): child for child in unit['children'] or []}
    assert set(children) == {read_policy[child] for child in expected.children}, f"{viewer}: children of {name}"
    for child in expected.children:
        assert_linked(read_policy, viewer, children[read_policy[child]], child)


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_units_by_id(client, login_token_factory, read_policy, viewer):
    result = await query(
        client, login_token_factory, read_policy, viewer, 'blocksUnits',
        f"query ($ids: [ID!]) {{ blocksUnits(ids: $ids) {{ status result {{ {UNIT_FIELDS} }} errors {{ name message }} }} }}",
        {'ids': [read_policy[name] for name in UNIT_PARENTS]}
    )
    units = {int(unit['id']): unit for unit in result}
    assert set(units) == {read_policy[name] for name in UNIT_PARENTS}
    for name in UNIT_PARENTS:
        assert_unit(read_policy, viewer, name, units[read_policy[name]])


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_blocks_at_locations(client, login_token_factory, read_policy, viewer):
    text = (
        f"query ($locations: [ID!]) {{ blocks(locationIds: $locations) {{ "
        f"  status result {{ {UNIT_FIELDS} }} errors {{ name message }} }} }}"
    )
    locations = ['field', 'field_registered', 'state']
    result = await query(
        client, login_token_factory, read_policy, viewer, 'blocks', text,
        {'locations': [read_policy[location] for location in locations]}
    )
    roots = {int(unit['id']): unit for unit in result}
    expected = {
        name for name in read_policy.shown_roots(viewer, UNIT_PARENTS) if UNIT_LOCATIONS.get(name) in locations
    }
    assert set(roots) == {read_policy[name] for name in expected}
    for name in expected:
        assert_unit(read_policy, viewer, name, roots[read_policy[name]])

    # without locations there is nothing to look in
    assert await query(client, login_token_factory, read_policy, viewer, 'blocks', text, {'locations': None}) == []


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_descendants_by_subject(client, login_token_factory, read_policy, viewer):
    result = await query(
        client, login_token_factory, read_policy, viewer, 'blocksDescendantsBySubject',
        "query ($ids: [ID!]!) { blocksDescendantsBySubject(unitIds: $ids) { "
        "  status result { subject { id } units { id name } } errors { name message } } }",
        {'ids': [read_policy['field_unit']]}
    )
    below = {name for name, parent in UNIT_PARENTS.items() if parent is not None and name != 'plant_private'}
    found = {int(unit['id']) for group in result for unit in group['units']}
    assert found == {read_policy[name] for name in below if read_policy.readable(viewer, name)}
    assert all(unit['name'] != REDACTED for group in result for unit in group['units'])
    assert all(group['subject'] is not None for group in result)
