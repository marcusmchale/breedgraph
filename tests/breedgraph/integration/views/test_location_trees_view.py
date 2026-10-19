"""
Location trees and layout trees under the read policy (docs/read-access.md), on the read-policy scenario:

    country (root, public) > state (child, private) > field (child, public) > centre (other, private)
        > lab (other, registered); state > field_registered (child, registered)
    country_private (child, private) > state_public (child, public)

    facility (root, public, at field) > chamber (child, private) > shelf (child, public)
    facility_private (child, private, at state) > room_public (child, public)

Hidden members are skipped and their readable descendants joined to the nearest readable ancestor (rule 3); a hidden
root is kept as a placeholder holding them (rule 4); any other hidden member asked for by id is a bare placeholder
(rule 2); searches leave hidden members out (rule 5).
"""
import pytest

from tests.breedgraph.scenarios.read_policy_scenario import VIEWERS, LOCATION_PARENTS, LAYOUT_PARENTS, LOCATION_COORDINATES

REDACTED = 'REDACTED'

LOCATION_TYPES = {
    'country': 'ontology_location_country', 'country_private': 'ontology_location_country',
    'state': 'ontology_location_state', 'state_public': 'ontology_location_state',
    'field': 'ontology_location_field', 'field_registered': 'ontology_location_field',
    'centre': 'ontology_location_research_centre', 'lab': 'ontology_location_lab',
}
LAYOUT_LOCATIONS = {'facility': 'field', 'facility_private': 'state'}
LAYOUT_POSITIONS = {'chamber': ['1'], 'shelf': ['rear', 'top', 'right'], 'room_public': ['1']}


def ids(read_policy, names) -> set[int]:
    return {read_policy[name] for name in names}


def assert_location(read_policy, viewer: str, name: str, location):
    expected = read_policy.tree_member(viewer, LOCATION_PARENTS, name)
    assert location.id == read_policy[name]
    if expected.readable:
        assert location.name != REDACTED, f"{viewer} should read {name}"
        assert location.type == read_policy[LOCATION_TYPES[name]]
        assert location.root == read_policy[expected.root]
        assert location.parent == (read_policy[expected.parent] if expected.parent else None), f"{viewer}: parent of {name}"
        assert [(c['latitude'], c['longitude']) for c in location.coordinates] == LOCATION_COORDINATES.get(name, [])
    else:
        assert location.name == REDACTED, f"{viewer} should not read {name}"
        assert location.type is None
        assert location.parent is None
        assert not location.coordinates, f"{viewer} should not see where {name} is"
        # a hidden root keeps its location tree, so its children can name it; other placeholders are bare
        assert location.root == (read_policy[name] if name == expected.root else None)
    assert set(location.children) == ids(read_policy, expected.children), f"{viewer}: children of {name}"


def assert_layout(read_policy, viewer: str, name: str, layout):
    expected = read_policy.tree_member(viewer, LAYOUT_PARENTS, name)
    assert layout.id == read_policy[name]
    is_root = name == expected.root
    if expected.readable:
        assert layout.name != REDACTED, f"{viewer} should read {name}"
        assert layout.axes
        assert layout.root == read_policy[expected.root]
        assert layout.parent == (read_policy[expected.parent] if expected.parent else None), f"{viewer}: parent of {name}"
        # a layout joined to an ancestor past a hidden parent has no position in it
        joined_directly = expected.parent is not None and expected.parent == LAYOUT_PARENTS[name]
        assert (layout.position or None) == (LAYOUT_POSITIONS[name] if joined_directly else None), \
            f"{viewer}: position of {name}"
    else:
        assert layout.name == REDACTED, f"{viewer} should not read {name}"
        assert not layout.axes
        assert layout.parent is None
        assert not layout.position
        assert layout.root == (read_policy[name] if is_root else None)
    # roots keep their location, even as placeholders
    assert layout.location == (read_policy[LAYOUT_LOCATIONS[name]] if is_root else None)
    assert set(layout.children) == ids(read_policy, expected.children), f"{viewer}: children of {name}"


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_location_trees(views_factory, read_policy, viewer):
    async with views_factory.get_views(user_id=read_policy.user(viewer)) as views:
        roots = {root.id: root for root in await views.location_trees.get_location_trees()}
    expected = read_policy.shown_roots(viewer, LOCATION_PARENTS)
    assert expected == {'country', 'country_private'}
    assert set(roots) == ids(read_policy, expected)
    for name in expected:
        assert_location(read_policy, viewer, name, roots[read_policy[name]])


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_locations_by_id(views_factory, read_policy, viewer):
    async with views_factory.get_views(user_id=read_policy.user(viewer)) as views:
        locations = await views.location_trees.get_locations([read_policy[name] for name in LOCATION_PARENTS])
    assert set(locations) == ids(read_policy, LOCATION_PARENTS)
    for name in LOCATION_PARENTS:
        assert_location(read_policy, viewer, name, locations[read_policy[name]])


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_search_leaves_hidden_locations_out(views_factory, read_policy, viewer):
    """A location is found by any part of its name, ignoring case, only by those who can read it (rule 5)"""
    names = {}
    for reader in ('admin', 'stranger'):  # between them, they read every location
        async with views_factory.get_views(user_id=read_policy.user(reader)) as views:
            located = await views.location_trees.get_locations([read_policy[name] for name in LOCATION_PARENTS])
        names.update({location.id: location.name for location in located.values() if location.name != REDACTED})
    assert set(names) == ids(read_policy, LOCATION_PARENTS)

    async with views_factory.get_views(user_id=read_policy.user(viewer)) as views:
        for name in LOCATION_PARENTS:
            text = names[read_policy[name]]
            # part of the name, or all of a name too short to have a middle (random names can be like 'S.')
            found = await views.location_trees.search_locations((text[1:-1].strip() or text).upper())
            readable = read_policy.tree_member(viewer, LOCATION_PARENTS, name).readable
            assert (read_policy[name] in {location.id for location in found}) == readable, f"{viewer}: search for {name}"
            # what is found is readable, in full
            for location in found:
                assert location.name != REDACTED
                assert_location(read_policy, viewer, next(n for n in LOCATION_PARENTS if read_policy[n] == location.id), location)
        assert len(await views.location_trees.search_locations(names[read_policy['country']], limit=1)) <= 1
        assert await views.location_trees.search_locations('  ') == []


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_locations_by_type(views_factory, read_policy, viewer):
    async with views_factory.get_views(user_id=read_policy.user(viewer)) as views:
        for type_key in set(LOCATION_TYPES.values()):
            locations = {
                location.id: location
                for location in await views.location_trees.get_locations_by_type(read_policy[type_key])
            }
            expected = [
                name for name, name_type in LOCATION_TYPES.items()
                if name_type == type_key and read_policy.readable(viewer, name)
            ]
            assert set(locations) == ids(read_policy, expected), f"{viewer}: locations of type {type_key}"
            for name in expected:
                assert_location(read_policy, viewer, name, locations[read_policy[name]])


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
@pytest.mark.parametrize('start', ('country', 'state', 'field', 'country_private'))
async def test_descendants_by_type(views_factory, read_policy, viewer, start):
    """Every readable location below, through hidden ones, by type; hidden ones left out"""
    descendants = set()
    pending = [start]
    while pending:
        parent = pending.pop()
        children = [name for name, name_parent in LOCATION_PARENTS.items() if name_parent == parent]
        descendants.update(children)
        pending.extend(children)
    expected: dict[int, set[int]] = {}
    # below a hidden location nothing, unless it is a location tree's root, whose placeholder holds the readable ones
    if read_policy.readable(viewer, start) or LOCATION_PARENTS.get(start) is None:
        for name in descendants:
            if read_policy.readable(viewer, name):
                expected.setdefault(read_policy[LOCATION_TYPES[name]], set()).add(read_policy[name])

    async with views_factory.get_views(user_id=read_policy.user(viewer)) as views:
        by_type = await views.location_trees.get_descendants_by_type([read_policy[start]])
    assert {type_id: {location.id for location in locations} for type_id, locations in by_type.items()} == expected
    for locations in by_type.values():
        assert all(location.name != REDACTED for location in locations)


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_layout_trees_at_location(views_factory, read_policy, viewer):
    async with views_factory.get_views(user_id=read_policy.user(viewer)) as views:
        for location, root in (('field', 'facility'), ('state', 'facility_private'), ('lab', None)):
            roots = {layout.id: layout for layout in await views.layout_trees.get_layout_trees(read_policy[location])}
            expected = {root} if root in read_policy.shown_roots(viewer, LAYOUT_PARENTS) else set()
            assert set(roots) == ids(read_policy, expected), f"{viewer}: layout trees at {location}"
            for name in expected:
                assert_layout(read_policy, viewer, name, roots[read_policy[name]])


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_layouts_by_id(views_factory, read_policy, viewer):
    async with views_factory.get_views(user_id=read_policy.user(viewer)) as views:
        layouts = await views.layout_trees.get_layouts([read_policy[name] for name in LAYOUT_PARENTS])
    assert set(layouts) == ids(read_policy, LAYOUT_PARENTS)
    for name in LAYOUT_PARENTS:
        assert_layout(read_policy, viewer, name, layouts[read_policy[name]])


@pytest.mark.asyncio(loop_scope="session")
async def test_missing_ids_are_left_out(views_factory, read_policy):
    missing = max(read_policy.ids.values()) + 1000
    async with views_factory.get_views(user_id=read_policy.user('admin')) as views:
        assert (await views.location_trees.get_locations([missing, read_policy['country']])).keys() == {read_policy['country']}
        assert await views.layout_trees.get_layouts([missing]) == {}
        assert await views.layout_trees.get_layout_trees(missing) == []
        assert await views.location_trees.get_descendants_by_type([missing]) == {}
