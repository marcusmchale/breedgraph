"""
The region and arrangement queries under the read policy, through GraphQL, on the read-policy scenario
(see tests/breedgraph/integration/views/test_regions_view.py for the views underneath).
They answer anonymous requests; a location's region, parent and children, and a layout's arrangement, parent,
children and location, resolve to the view's locations and layouts, placeholders included.
"""
import pytest

from breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus

from tests.breedgraph.e2e.utils import post_as, get_verified_payload
from tests.breedgraph.scenarios.read_policy_scenario import VIEWERS, LOCATION_PARENTS, LAYOUT_PARENTS

REDACTED = 'REDACTED'

LOCATION_FIELDS = "id name type { id } region { id name } parent { id name } children { id name }"
LAYOUT_FIELDS = (
    "id name axes position arrangement { id name } parent { id name } children { id name } location { id name }"
)
LAYOUT_LOCATIONS = {'facility': 'field', 'facility_private': 'state'}


async def query(client, login_token_factory, read_policy, viewer: str, operation: str, text: str, variables=None):
    response = await post_as(client, login_token_factory, read_policy.user(viewer), text, variables)
    payload = get_verified_payload(response, operation)
    # an empty list is a valid result here, so not assert_payload_success
    assert payload['status'] == GQLStatus.SUCCESS.name, payload['errors']
    assert payload['errors'] is None
    return payload['result']


def assert_linked(read_policy, viewer: str, linked: dict | None, name: str | None):
    """A linked location or layout, by its name in the scenario, named only where the viewer can read it"""
    if name is None:
        assert linked is None
        return
    assert int(linked['id']) == read_policy[name]
    assert (linked['name'] != REDACTED) == read_policy.readable(viewer, name), f"{viewer}: {name} as linked"


def assert_location(read_policy, viewer: str, name: str, location: dict):
    expected = read_policy.tree_member(viewer, LOCATION_PARENTS, name)
    assert int(location['id']) == read_policy[name]
    assert (location['name'] != REDACTED) == expected.readable, f"{viewer}: {name}"
    if expected.readable:
        assert location['type'] is not None
    is_kept = expected.readable or name == expected.root
    assert_linked(read_policy, viewer, location['region'], expected.root if is_kept else None)
    assert_linked(read_policy, viewer, location['parent'], expected.parent)
    children = {int(child['id']): child for child in location['children'] or []}
    assert set(children) == {read_policy[child] for child in expected.children}, f"{viewer}: children of {name}"
    for child in expected.children:
        assert_linked(read_policy, viewer, children[read_policy[child]], child)


def assert_layout(read_policy, viewer: str, name: str, layout: dict):
    expected = read_policy.tree_member(viewer, LAYOUT_PARENTS, name)
    assert int(layout['id']) == read_policy[name]
    assert (layout['name'] != REDACTED) == expected.readable, f"{viewer}: {name}"
    is_root = name == expected.root
    is_kept = expected.readable or is_root
    assert_linked(read_policy, viewer, layout['arrangement'], expected.root if is_kept else None)
    assert_linked(read_policy, viewer, layout['parent'], expected.parent)
    children = {int(child['id']): child for child in layout['children'] or []}
    assert set(children) == {read_policy[child] for child in expected.children}, f"{viewer}: children of {name}"
    # a root's location resolves, as a placeholder where the viewer cannot read it
    assert_linked(read_policy, viewer, layout['location'], LAYOUT_LOCATIONS[name] if is_root else None)


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_regions(client, login_token_factory, read_policy, viewer):
    result = await query(
        client, login_token_factory, read_policy, viewer, 'regions',
        f"query {{ regions {{ status result {{ {LOCATION_FIELDS} }} errors {{ name message }} }} }}"
    )
    roots = {int(location['id']): location for location in result}
    expected = read_policy.shown_roots(viewer, LOCATION_PARENTS)
    assert set(roots) == {read_policy[name] for name in expected}
    for name in expected:
        assert_location(read_policy, viewer, name, roots[read_policy[name]])


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_locations_by_id(client, login_token_factory, read_policy, viewer):
    result = await query(
        client, login_token_factory, read_policy, viewer, 'regionsLocations',
        f"query ($ids: [ID!]!) {{ regionsLocations(ids: $ids) {{ status result {{ {LOCATION_FIELDS} }} errors {{ name message }} }} }}",
        {'ids': [read_policy[name] for name in LOCATION_PARENTS]}
    )
    locations = {int(location['id']): location for location in result}
    assert set(locations) == {read_policy[name] for name in LOCATION_PARENTS}
    for name in LOCATION_PARENTS:
        assert_location(read_policy, viewer, name, locations[read_policy[name]])


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_locations_by_type(client, login_token_factory, read_policy, viewer):
    result = await query(
        client, login_token_factory, read_policy, viewer, 'regionsLocationsByType',
        f"query ($type: ID!) {{ regionsLocationsByType(locationTypeId: $type) {{ status result {{ {LOCATION_FIELDS} }} errors {{ name message }} }} }}",
        {'type': read_policy['ontology_location_field']}
    )
    expected = [name for name in ('field', 'field_registered') if read_policy.readable(viewer, name)]
    locations = {int(location['id']): location for location in result or []}
    assert set(locations) == {read_policy[name] for name in expected}
    for name in expected:
        assert_location(read_policy, viewer, name, locations[read_policy[name]])


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_descendants_by_type(client, login_token_factory, read_policy, viewer):
    result = await query(
        client, login_token_factory, read_policy, viewer, 'regionsDescendantsByType',
        "query ($ids: [ID!]!) { regionsDescendantsByType(locationIds: $ids) { "
        "  status result { type { id } locations { id name } } errors { name message } } }",
        {'ids': [read_policy['country']]}
    )
    found = {int(location['id']) for group in result or [] for location in group['locations']}
    below_country = [name for name in LOCATION_PARENTS if name not in ('country', 'country_private', 'state_public')]
    assert found == {read_policy[name] for name in below_country if read_policy.readable(viewer, name)}
    assert all(location['name'] != REDACTED for group in result or [] for location in group['locations'])
    assert all(group['type'] is not None for group in result or [])


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
@pytest.mark.parametrize('location, root', (('field', 'facility'), ('state', 'facility_private')))
async def test_arrangements(client, login_token_factory, read_policy, viewer, location, root):
    result = await query(
        client, login_token_factory, read_policy, viewer, 'arrangements',
        f"query ($location: ID!) {{ arrangements(locationId: $location) {{ status result {{ {LAYOUT_FIELDS} }} errors {{ name message }} }} }}",
        {'location': read_policy[location]}
    )
    roots = {int(layout['id']): layout for layout in result or []}
    expected = {root} if root in read_policy.shown_roots(viewer, LAYOUT_PARENTS) else set()
    assert set(roots) == {read_policy[name] for name in expected}
    for name in expected:
        assert_layout(read_policy, viewer, name, roots[read_policy[name]])


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_layouts_by_id(client, login_token_factory, read_policy, viewer):
    result = await query(
        client, login_token_factory, read_policy, viewer, 'arrangementsLayouts',
        f"query ($ids: [ID!]) {{ arrangementsLayouts(ids: $ids) {{ status result {{ {LAYOUT_FIELDS} }} errors {{ name message }} }} }}",
        {'ids': [read_policy[name] for name in LAYOUT_PARENTS]}
    )
    layouts = {int(layout['id']): layout for layout in result}
    assert set(layouts) == {read_policy[name] for name in LAYOUT_PARENTS}
    for name in LAYOUT_PARENTS:
        assert_layout(read_policy, viewer, name, layouts[read_policy[name]])
