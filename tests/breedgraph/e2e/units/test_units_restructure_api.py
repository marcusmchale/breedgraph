"""
Changing how units hang together through unitsUpdateUnit: children changed within a unit graph, a child only the unit
held split off as the root of a unit graph of its own, and another unit graph merged in below a unit, by a child or by
giving its root parents, its units keeping their controls. Aliased unitsRoots fields in one request each return their
own roots.
"""
import pytest

from breedgraph.domain.model.controls import ReadRelease
from breedgraph.domain.model.unit_graphs import UnitInput, Position
from tests.breedgraph.e2e.utils import post_as, get_verified_payload, assert_payload_success

UPDATE = """
mutation ($unit: UnitUpdate!) {
  unitsUpdateUnit(unit: $unit) { status result errors { name message } }
}
"""
UNITS = """
query ($ids: [ID!]) {
  unitsUnits(ids: $ids) { status result { id name parents { id } children { id } } errors { name message } }
}
"""
RELEASES = """
query ($ids: [ID!]!) {
  controlsControllers(entityLabel: UNIT, entityIds: $ids) { status result { release } errors { name message } }
}
"""
ROOTS = """
query ($a: [ID!], $b: [ID!]) {
  a: unitsRoots(locationIds: $a) { status result { id } errors { name message } }
  b: unitsRoots(locationIds: $b) { status result { id } errors { name message } }
}
"""


async def _unit_graph(uow_factory, context, parents_by_name: dict, location_id: int | None = None,
                      release: ReadRelease = ReadRelease.PRIVATE) -> dict:
    """
    A unit graph of units positioned at the location, the first named its root and each later one below its parents
    by name; the ids by name
    """
    user_id, team_id = context['user_id'], context['team_id']
    location_id = location_id or context['location_id']
    subject = context['ontology_subject_tree']
    names = list(parents_by_name)

    def unit_input(name):
        return UnitInput(name=name, subject=subject, positions=[Position(location_id=location_id)])

    async with uow_factory.get_uow(user_id=user_id, write_team=team_id, release=release) as uow:
        unit_graph = await uow.repositories.unit_graphs.create(unit_input(names[0]))
        temp_ids = {names[0]: unit_graph.get_root_id()}
        for name in names[1:]:
            temp_ids[name] = unit_graph.add_unit(
                unit_input(name), parents=[temp_ids[parent] for parent in parents_by_name[name]]
            )
        await uow.commit()
        root_id = unit_graph.get_root_id()
    async with uow_factory.get_uow(user_id=user_id) as uow:
        unit_graph = await uow.repositories.unit_graphs.get(unit_id=root_id)
        return {unit.name: unit.id for unit in unit_graph.entries.values()}


async def _post(client, login_token_factory, context, query: str, variables: dict, name: str) -> dict:
    payload = get_verified_payload(
        await post_as(client, login_token_factory, context['user_id'], query, variables), name
    )
    assert_payload_success(payload)
    return payload


async def _update(client, login_token_factory, context, unit: dict):
    await _post(client, login_token_factory, context, UPDATE, {'unit': unit}, 'unitsUpdateUnit')


async def _units(client, login_token_factory, context, ids: list) -> dict:
    """{ name: { parents, children } } of the units, as sets of ids"""
    payload = await _post(client, login_token_factory, context, UNITS, {'ids': ids}, 'unitsUnits')
    return {
        unit['name']: {
            'parents': {int(parent['id']) for parent in unit['parents']},
            'children': {int(child['id']) for child in unit['children']}
        }
        for unit in payload['result']
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_children_change_within_a_unit_graph(client, login_token_factory, uow_factory, unit_graph_build_context):
    context = unit_graph_build_context
    ids = await _unit_graph(uow_factory, context, {
        'Field': [], 'Plot 1': ['Field'], 'Plot 2': ['Field'], 'Tree': ['Plot 1', 'Plot 2']
    })
    # Plot 1 lets the tree go, which Plot 2 still holds, and takes Plot 2 below it
    await _update(client, login_token_factory, context, {'id': ids['Plot 1'], 'childrenIds': [ids['Plot 2']]})
    units = await _units(client, login_token_factory, context, list(ids.values()))
    assert units['Plot 1']['children'] == {ids['Plot 2']}
    assert units['Plot 2']['parents'] == {ids['Field'], ids['Plot 1']}
    assert units['Tree']['parents'] == {ids['Plot 2']}


@pytest.mark.asyncio(loop_scope="session")
async def test_a_child_only_the_unit_holds_is_split_off(client, login_token_factory, uow_factory, unit_graph_build_context):
    context = unit_graph_build_context
    ids = await _unit_graph(uow_factory, context, {'Split field': [], 'Split tree': ['Split field'], 'Split leaf': ['Split tree']})
    await _update(client, login_token_factory, context, {'id': ids['Split field'], 'childrenIds': []})
    units = await _units(client, login_token_factory, context, list(ids.values()))
    assert units['Split field']['children'] == set()
    assert units['Split tree']['parents'] == set()
    assert units['Split tree']['children'] == {ids['Split leaf']}
    roots = await _post(client, login_token_factory, context, ROOTS, {'a': [context['location_id']], 'b': []}, 'a')
    assert str(ids['Split tree']) in {root['id'] for root in roots['result']}


@pytest.mark.asyncio(loop_scope="session")
async def test_a_unit_graph_merged_in_by_a_child_keeps_its_controls(client, login_token_factory, uow_factory, unit_graph_build_context):
    context = unit_graph_build_context
    ids_a = await _unit_graph(uow_factory, context, {'Field A': [], 'Plot A': ['Field A']})
    ids_b = await _unit_graph(uow_factory, context, {'Field B': [], 'Tree B': ['Field B']}, release=ReadRelease.REGISTERED)
    await _update(client, login_token_factory, context, {'id': ids_a['Plot A'], 'childrenIds': [ids_b['Field B']]})
    units = await _units(client, login_token_factory, context, [ids_b['Field B']])
    assert units['Field B']['parents'] == {ids_a['Plot A']}
    releases = await _post(client, login_token_factory, context, RELEASES, {'ids': list(ids_b.values())}, 'controlsControllers')
    assert [controller['release'] for controller in releases['result']] == ['REGISTERED', 'REGISTERED']


@pytest.mark.asyncio(loop_scope="session")
async def test_a_root_given_parents_is_merged_in_below_them(client, login_token_factory, uow_factory, unit_graph_build_context):
    """A merge by parents was refused for want of a write team, as the merged units were given new controls"""
    context = unit_graph_build_context
    ids_a = await _unit_graph(uow_factory, context, {'Field C': [], 'Plot C': ['Field C']})
    ids_b = await _unit_graph(uow_factory, context, {'Field D': [], 'Tree D': ['Field D']}, release=ReadRelease.REGISTERED)
    await _update(client, login_token_factory, context, {'id': ids_b['Field D'], 'parentIds': [ids_a['Plot C']]})
    units = await _units(client, login_token_factory, context, [ids_b['Field D']])
    assert units['Field D']['parents'] == {ids_a['Plot C']}
    releases = await _post(client, login_token_factory, context, RELEASES, {'ids': list(ids_b.values())}, 'controlsControllers')
    assert [controller['release'] for controller in releases['result']] == ['REGISTERED', 'REGISTERED']


@pytest.mark.asyncio(loop_scope="session")
async def test_aliased_roots_queries_return_their_own_roots(client, login_token_factory, uow_factory, unit_graph_build_context):
    context = unit_graph_build_context
    field_ids = await _unit_graph(uow_factory, context, {'Alias field': []})
    lab_ids = await _unit_graph(uow_factory, context, {'Alias lab': []}, location_id=context['location_lab_id'])
    body = (await post_as(client, login_token_factory, context['user_id'], ROOTS, {
        'a': [context['location_id']], 'b': [context['location_lab_id']]
    })).json()['data']
    field_roots = {root['id'] for root in body['a']['result']}
    lab_roots = {root['id'] for root in body['b']['result']}
    assert str(field_ids['Alias field']) in field_roots and str(field_ids['Alias field']) not in lab_roots
    assert str(lab_ids['Alias lab']) in lab_roots and str(lab_ids['Alias lab']) not in field_roots
