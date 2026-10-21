"""
Units under the read policy (docs/read-access.md), on the read-policy scenario:

    field_unit (child, private, at field) > tree_public (child, public, at state) > leaf_private (child, private)
        > rhizosphere_public (child, public); tree_public > leaf_other (other, private) > rhizosphere_other
        (other, registered); field_unit > tree_registered (child, registered)
    plot_public (root, public, at field_registered) > plant_private (child, private)
    plot_private (child, private, at field), holding nothing

Hidden units are skipped and their readable descendants joined to the nearest readable ancestor (rule 3); a hidden
unit graph root is kept as a placeholder holding them (rule 4); any other hidden unit asked for by id is a bare placeholder
(rule 2); searches leave hidden units out (rule 5).
"""
import pytest

from tests.breedgraph.scenarios.read_policy_scenario import VIEWERS, UNIT_PARENTS

REDACTED = 'REDACTED'

UNIT_SUBJECTS = {
    'field_unit': 'ontology_subject_field', 'plot_public': 'ontology_subject_field',
    'plot_private': 'ontology_subject_field',
    'tree_public': 'ontology_subject_tree', 'tree_registered': 'ontology_subject_tree',
    'plant_private': 'ontology_subject_tree',
    'leaf_private': 'ontology_subject_leaf', 'leaf_other': 'ontology_subject_leaf',
    'rhizosphere_public': 'ontology_subject_rhizosphere', 'rhizosphere_other': 'ontology_subject_rhizosphere',
}
UNIT_LOCATIONS = {'field_unit': 'field', 'tree_public': 'state', 'plot_public': 'field_registered', 'plot_private': 'field'}
UNIT_GERMPLASM = {'tree_public': 'crop_leaf', 'tree_registered': 'crop_middle'}


def ids(read_policy, names) -> set[int]:
    return {read_policy[name] for name in names}


def descendants(name: str) -> set[str]:
    found, pending = set(), [name]
    while pending:
        current = pending.pop()
        children = [member for member, parent in UNIT_PARENTS.items() if parent == current]
        found.update(children)
        pending.extend(children)
    return found


def assert_unit(read_policy, viewer: str, name: str, unit):
    expected = read_policy.tree_member(viewer, UNIT_PARENTS, name)
    assert unit.id == read_policy[name]
    if expected.readable:
        assert unit.name != REDACTED, f"{viewer} should read {name}"
        assert unit.subject == read_policy[UNIT_SUBJECTS[name]]
        # references to other aggregates are kept whether or not the viewer can read them (rule 2)
        assert unit.germplasm == (read_policy[UNIT_GERMPLASM[name]] if name in UNIT_GERMPLASM else None)
        assert [position.location_id for position in unit.positions] == (
            [read_policy[UNIT_LOCATIONS[name]]] if name in UNIT_LOCATIONS else []
        )
        assert unit.parents == ([read_policy[expected.parent]] if expected.parent else []), f"{viewer}: parents of {name}"
    else:
        assert unit.name == REDACTED, f"{viewer} should not read {name}"
        assert unit.subject is None
        assert unit.germplasm is None
        assert unit.positions == []
        assert unit.parents == []
    assert set(unit.children) == ids(read_policy, expected.children), f"{viewer}: children of {name}"


def test_expected_shapes(read_policy):
    """The scenario gives the viewers different unit graphs, so the tests below are not vacuous"""
    assert read_policy.shown_roots('admin', UNIT_PARENTS) == {'field_unit', 'plot_public', 'plot_private'}
    assert read_policy.shown_roots('outsider', UNIT_PARENTS) == {'field_unit', 'plot_public'}
    assert read_policy.tree_member('outsider', UNIT_PARENTS, 'tree_public').children == {'rhizosphere_public', 'rhizosphere_other'}
    assert read_policy.tree_member('anonymous', UNIT_PARENTS, 'tree_public').children == {'rhizosphere_public'}
    assert read_policy.tree_member('admin', UNIT_PARENTS, 'tree_public').children == {'leaf_private', 'rhizosphere_other'}


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_units_by_id(views_factory, read_policy, viewer):
    async with views_factory.get_views(user_id=read_policy.user(viewer)) as views:
        units = await views.units.get_units([read_policy[name] for name in UNIT_PARENTS])
    assert set(units) == ids(read_policy, UNIT_PARENTS)
    for name in UNIT_PARENTS:
        assert_unit(read_policy, viewer, name, units[read_policy[name]])


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
@pytest.mark.parametrize('location', ('field', 'field_registered', 'state'))
async def test_unit_graph_roots(views_factory, read_policy, viewer, location):
    """
    Roots positioned at a location, kept where the viewer can read a unit in the unit graph; only roots count, and none
    at a location the viewer cannot read (a search from it, docs/read-access.md rule 5)
    """
    async with views_factory.get_views(user_id=read_policy.user(viewer)) as views:
        roots = {unit.id: unit for unit in await views.units.get_unit_graph_roots([read_policy[location]])}
    expected = {
        name for name in read_policy.shown_roots(viewer, UNIT_PARENTS) if UNIT_LOCATIONS.get(name) == location
    } if read_policy.readable(viewer, location) else set()
    assert set(roots) == ids(read_policy, expected), f"{viewer}: unit graph roots at {location}"
    for name in expected:
        assert_unit(read_policy, viewer, name, roots[read_policy[name]])


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_unit_names(views_factory, read_policy, viewer):
    async with views_factory.get_views(user_id=read_policy.user(viewer)) as views:
        units = await views.units.get_unit_names([read_policy[name] for name in UNIT_PARENTS])
    assert set(units) == ids(read_policy, UNIT_PARENTS)
    for name in UNIT_PARENTS:
        unit = units[read_policy[name]]
        if read_policy.readable(viewer, name):
            assert unit.name != REDACTED
            assert unit.germplasm == (read_policy[UNIT_GERMPLASM[name]] if name in UNIT_GERMPLASM else None)
        else:
            assert unit.name == REDACTED
            assert unit.germplasm is None


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
@pytest.mark.parametrize('start', ('field_unit', 'tree_public', 'leaf_other', 'plot_public', 'plot_private'))
async def test_descendants_by_subject(views_factory, read_policy, viewer, start):
    """
    Every readable unit below, through hidden ones, by subject; hidden ones left out. Below a hidden unit nothing,
    unless it is a unit graph's root, whose placeholder holds the readable units below it
    """
    expected: dict[int, set[int]] = {}
    if read_policy.readable(viewer, start) or UNIT_PARENTS.get(start) is None:
        for name in descendants(start):
            if read_policy.readable(viewer, name):
                expected.setdefault(read_policy[UNIT_SUBJECTS[name]], set()).add(read_policy[name])
    async with views_factory.get_views(user_id=read_policy.user(viewer)) as views:
        by_subject = await views.units.get_descendants_by_subject([read_policy[start]])
    assert {subject: {unit.id for unit in units} for subject, units in by_subject.items()} == expected
    assert all(unit.name != REDACTED for units in by_subject.values() for unit in units)


@pytest.mark.asyncio(loop_scope="session")
async def test_missing_ids_are_left_out(views_factory, read_policy):
    missing = max(read_policy.ids.values()) + 1000
    async with views_factory.get_views(user_id=read_policy.user('admin')) as views:
        assert (await views.units.get_units([missing, read_policy['tree_public']])).keys() == {read_policy['tree_public']}
        assert await views.units.get_unit_names([missing]) == {}
        assert await views.units.get_unit_graph_roots([missing]) == []
        assert await views.units.get_descendants_by_subject([missing]) == {}
