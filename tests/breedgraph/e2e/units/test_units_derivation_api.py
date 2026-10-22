"""
Units derived from others through GraphQL (README, Unit), on the arrivals scenario
(tests/breedgraph/scenarios/arrival_scenario.py): plantlets in the stranger's own unit graph grown from samples that
arrived at the lab in the child team's. A derivation passes nothing down, so a derived unit takes no germplasm from the
unit it came from; linking needs read access to it, a hidden source shows as a placeholder, and derivatives list only
units the viewer can read. A unit is not derived from its own context, nor from a unit derived from it, and a unit with
derivatives can't be deleted.
"""
import pytest

from breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus

from tests.breedgraph.e2e.utils import post_as, get_verified_payload

CREATE = """
mutation ($unit: UnitInput!, $controlTeamId: ID!, $release: ReadRelease, $position: PositionInput) {
  unitsCreateUnit(unit: $unit, controlTeamId: $controlTeamId, release: $release, position: $position) {
    status result errors { name message }
  }
}
"""
UPDATE = """
mutation ($unit: UnitUpdate!) {
  unitsUpdateUnit(unit: $unit) { status result errors { name message } }
}
"""
DELETE = """
mutation ($id: ID!) {
  unitsDeleteUnit(id: $id) { status result errors { name message } }
}
"""
ROOTS = """
query ($locationIds: [ID!]) {
  unitsRoots(locationIds: $locationIds) { status result { id name } errors { name message } }
}
"""
UNITS = """
query ($ids: [ID!]) {
  unitsUnits(ids: $ids) {
    status errors { name message }
    result {
      id name
      parents { id }
      inheritedGermplasm { germplasm { id } }
      derivedFrom { unit { id name } sourceType description }
      derivatives { unit { id name } sourceType description }
    }
  }
}
"""


async def post(client, login_token_factory, user_id, text: str, variables: dict, operation: str) -> dict:
    return get_verified_payload(await post_as(client, login_token_factory, user_id, text, variables), operation)


async def succeeds(client, login_token_factory, user_id, text: str, variables: dict, operation: str):
    payload = await post(client, login_token_factory, user_id, text, variables, operation)
    assert payload['status'] == GQLStatus.SUCCESS.name, payload['errors']
    return payload['result']


async def fails(client, login_token_factory, user_id, text: str, variables: dict, operation: str) -> str:
    payload = await post(client, login_token_factory, user_id, text, variables, operation)
    assert payload['status'] != GQLStatus.SUCCESS.name
    return ' '.join(error['message'] for error in payload['errors'])


async def read(client, login_token_factory, user_id, unit_id: int) -> dict:
    (unit,) = await succeeds(client, login_token_factory, user_id, UNITS, {'ids': [unit_id]}, 'unitsUnits')
    return unit


async def field_season(client, login_token_factory, read_policy, name: str) -> int:
    """A field-season unit of the stranger's at field_registered, REGISTERED: the root plantlets are planted under"""
    stranger = read_policy['stranger']
    await succeeds(client, login_token_factory, stranger, CREATE, {
        'unit': {'subjectId': read_policy['ontology_subject_field'], 'name': name},
        'controlTeamId': read_policy['other'],
        'release': 'REGISTERED',
        'position': {'locationId': read_policy['field_registered']}
    }, 'unitsCreateUnit')
    roots = await succeeds(client, login_token_factory, stranger, ROOTS, {
        'locationIds': [read_policy['field_registered']]
    }, 'unitsRoots')
    (root_id,) = [int(root['id']) for root in roots if root['name'] == name]
    return root_id


async def plantlet(client, login_token_factory, read_policy, parent_id: int, name: str, derived_from: list) -> int:
    """A plantlet of the stranger's under parent_id, REGISTERED, derived from the units given; its id, by its name"""
    stranger = read_policy['stranger']
    await succeeds(client, login_token_factory, stranger, CREATE, {
        'unit': {
            'subjectId': read_policy['ontology_subject_tree'], 'name': name, 'parentIds': [parent_id],
            'derivedFrom': derived_from
        },
        'controlTeamId': read_policy['other'],
        'release': 'REGISTERED'
    }, 'unitsCreateUnit')
    parent = await succeeds(client, login_token_factory, stranger, """
        query ($ids: [ID!]) { unitsUnits(ids: $ids) { status result { children { id name } } errors { message } } }
    """, {'ids': [parent_id]}, 'unitsUnits')
    (unit_id,) = [int(child['id']) for child in parent[0]['children'] if child['name'] == name]
    return unit_id


@pytest.mark.asyncio(loop_scope="session")
async def test_a_plantlet_derived_from_an_arrival_in_a_unit_graph_of_its_own(
        client, login_token_factory, read_policy, arrivals
):
    stranger, writer = read_policy['stranger'], read_policy['writer']
    sample = arrivals.units['Arrival Sample B1']
    field_id = await field_season(client, login_token_factory, read_policy, 'Derived Field 2025')
    plantlet_id = await plantlet(client, login_token_factory, read_policy, field_id, 'Derived Plantlet B1', [
        {'unitId': sample, 'sourceType': 'TISSUE', 'description': 'Microcutting'}
    ])

    found = await read(client, login_token_factory, stranger, plantlet_id)
    assert found['parents'] == [{'id': str(field_id)}]
    assert found['derivedFrom'] == [{
        'unit': {'id': str(sample), 'name': 'Arrival Sample B1'}, 'sourceType': 'TISSUE', 'description': 'Microcutting'
    }]
    # the sample takes germplasm from its tree, but nothing comes down a derivation
    assert found['inheritedGermplasm'] is None
    assert (await read(client, login_token_factory, writer, sample))['inheritedGermplasm'] is not None

    for viewer in (stranger, writer):
        source = await read(client, login_token_factory, viewer, sample)
        assert source['derivatives'] == [{
            'unit': {'id': str(plantlet_id), 'name': 'Derived Plantlet B1'}, 'sourceType': 'TISSUE',
            'description': 'Microcutting'
        }]

    # given as an empty list, the derivations are removed; omitted, they are unchanged
    await succeeds(client, login_token_factory, stranger, UPDATE, {
        'unit': {'id': plantlet_id, 'name': 'Derived Plantlet B1 renamed'}
    }, 'unitsUpdateUnit')
    assert len((await read(client, login_token_factory, stranger, plantlet_id))['derivedFrom']) == 1
    await succeeds(client, login_token_factory, stranger, UPDATE, {
        'unit': {'id': plantlet_id, 'derivedFrom': []}
    }, 'unitsUpdateUnit')
    assert (await read(client, login_token_factory, stranger, plantlet_id))['derivedFrom'] == []
    assert (await read(client, login_token_factory, stranger, sample))['derivatives'] == []


@pytest.mark.asyncio(loop_scope="session")
async def test_a_derivation_needs_read_access_and_shows_hidden_units_as_placeholders(
        client, login_token_factory, read_policy, arrivals
):
    stranger, writer = read_policy['stranger'], read_policy['writer']
    hidden = read_policy['leaf_private']
    field_id = await field_season(client, login_token_factory, read_policy, 'Derived Field Hidden')
    await fails(client, login_token_factory, stranger, CREATE, {
        'unit': {
            'subjectId': read_policy['ontology_subject_tree'], 'name': 'Derived From Hidden',
            'parentIds': [field_id], 'derivedFrom': [{'unitId': hidden}]
        },
        'controlTeamId': read_policy['other']
    }, 'unitsCreateUnit')

    # the writer, who reads the hidden leaf, derives a unit of the child team's from it
    await succeeds(client, login_token_factory, writer, CREATE, {
        'unit': {
            'subjectId': read_policy['ontology_subject_tree'], 'name': 'Derived From Hidden',
            'derivedFrom': [{'unitId': hidden, 'sourceType': 'SEED'}]
        },
        'controlTeamId': read_policy['child'],
        'release': 'REGISTERED',
        'position': {'locationId': read_policy['field_registered']}
    }, 'unitsCreateUnit')
    source = await read(client, login_token_factory, writer, hidden)
    (derivative,) = source['derivatives']
    assert derivative['unit']['name'] == 'Derived From Hidden' and derivative['sourceType'] == 'SEED'
    derived_id = int(derivative['unit']['id'])

    # the stranger reads the derived unit, its source a placeholder, and finds nothing derived from the hidden leaf
    found = await read(client, login_token_factory, stranger, derived_id)
    assert found['derivedFrom'] == [{
        'unit': {'id': str(hidden), 'name': 'REDACTED'}, 'sourceType': 'SEED', 'description': None
    }]
    assert (await read(client, login_token_factory, stranger, hidden))['derivatives'] == []


@pytest.mark.asyncio(loop_scope="session")
async def test_derivations_refused(client, login_token_factory, read_policy, arrivals):
    stranger, writer = read_policy['stranger'], read_policy['writer']
    sample_a1, tree_a = arrivals.units['Arrival Sample A1'], arrivals.units['Arrival Tree A']
    # a leaf, with no position of its own: not in an arrival, whose counts another test asserts
    leaf_c = arrivals.units['Arrival Leaf C']

    async def update_refused(user_id, unit_id: int, derived_from: list) -> str:
        return await fails(client, login_token_factory, user_id, UPDATE, {
            'unit': {'id': unit_id, 'derivedFrom': derived_from}
        }, 'unitsUpdateUnit')

    # its own context: itself, and the units above or below it
    assert 'itself' in await update_refused(writer, sample_a1, [{'unitId': sample_a1}])
    assert 'context' in await update_refused(writer, sample_a1, [{'unitId': tree_a}])
    assert 'context' in await update_refused(writer, tree_a, [{'unitId': sample_a1}])
    assert 'once' in await update_refused(writer, leaf_c, [{'unitId': tree_a}, {'unitId': tree_a}])

    # a unit derived from it, directly or through another
    field_id = await field_season(client, login_token_factory, read_policy, 'Derived Field Refused')
    first = await plantlet(client, login_token_factory, read_policy, field_id, 'Derived Plantlet C', [
        {'unitId': leaf_c}
    ])
    second = await plantlet(client, login_token_factory, read_policy, field_id, 'Derived Plantlet C cutting', [
        {'unitId': first, 'sourceType': 'TISSUE'}
    ])
    assert 'derived from it' in await update_refused(writer, leaf_c, [{'unitId': second}])
    assert 'derived from it' in await update_refused(stranger, first, [{'unitId': leaf_c}, {'unitId': second}])

    # a unit with derivatives keeps them
    assert 'derived from this unit' in await fails(
        client, login_token_factory, writer, DELETE, {'id': leaf_c}, 'unitsDeleteUnit'
    )
    assert 'derived from this unit' in await fails(
        client, login_token_factory, stranger, DELETE, {'id': first}, 'unitsDeleteUnit'
    )
    # the last in a line of derivations can go, and its link with it
    await succeeds(client, login_token_factory, stranger, DELETE, {'id': second}, 'unitsDeleteUnit')
    assert (await read(client, login_token_factory, stranger, first))['derivatives'] == []
