"""
Children added to several units at once through GraphQL (unitsAddChildren), on the arrivals scenario
(tests/breedgraph/scenarios/arrival_scenario.py), e.g. a sampling event: leaves taken from the trees of a field on one
day, each named from its tree and placed where its tree was then, so they are not an arrival there. A parent's place is
its own position then or the one it takes from the units above it; one that can't be told is refused, as are too many
children, names that would repeat, and parents the user can't read. Without a start, the children are where their
parents are. Each test adds to units no other test here asserts on.
"""
import pytest

from breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus

from tests.breedgraph.e2e.utils import post_as, get_verified_payload
from tests.breedgraph.scenarios.arrival_scenario import LAB, FIELD

ADD_CHILDREN = """
mutation (
  $parents: UnitsSelection!, $subjectId: ID!, $count: Int, $name: String, $germplasmId: ID, $start: DateTime,
  $controlTeamId: ID!, $release: ReadRelease
) {
  unitsAddChildren(
    parents: $parents, subjectId: $subjectId, count: $count, name: $name, germplasmId: $germplasmId, start: $start,
    controlTeamId: $controlTeamId, release: $release
  ) {
    status errors { name message }
    result {
      id name subject { id } parents { id }
      germplasm { id } inheritedGermplasm { germplasm { id } }
      positions { location { id } layout { id } coordinates start end }
    }
  }
}
"""
# without $name, for the default
ADD_CHILDREN_DEFAULT_NAME = ADD_CHILDREN.replace(', $name: String', '').replace(' name: $name,', '')
ARRIVALS = """
query ($locationIds: [ID!]!) {
  unitsArrivals(locationIds: $locationIds) { status errors { message } result { location { id } start unitCount } }
}
"""


async def post(client, login_token_factory, user_id, text: str, variables: dict, operation: str) -> dict:
    return get_verified_payload(await post_as(client, login_token_factory, user_id, text, variables), operation)


async def added(client, login_token_factory, user_id, variables: dict, text: str = ADD_CHILDREN) -> list:
    payload = await post(client, login_token_factory, user_id, text, variables, 'unitsAddChildren')
    assert payload['status'] == GQLStatus.SUCCESS.name, payload['errors']
    return payload['result']


async def refused(client, login_token_factory, user_id, variables: dict) -> str:
    payload = await post(client, login_token_factory, user_id, ADD_CHILDREN, variables, 'unitsAddChildren')
    assert payload['status'] != GQLStatus.SUCCESS.name, payload
    return ' '.join(error['message'] for error in payload['errors'])


def places(unit: dict) -> list:
    return [
        (int(p['location']['id']), p['layout'] and int(p['layout']['id']), p['coordinates'], p['start'], p['end'])
        for p in unit['positions']
    ]


@pytest.mark.asyncio(loop_scope="session")
async def test_leaves_taken_from_trees_on_one_day(client, login_token_factory, read_policy, arrivals):
    writer = read_policy['writer']
    tree_a, tree_c = arrivals.units['Arrival Tree A'], arrivals.units['Arrival Tree C']
    children = await added(client, login_token_factory, writer, {
        'parents': {'unitIds': [tree_a, tree_c]},
        'subjectId': read_policy['ontology_subject_leaf'],
        'count': 2,
        'start': '2025-05-03',
        'controlTeamId': read_policy['child'],
        'release': 'REGISTERED'
    }, ADD_CHILDREN_DEFAULT_NAME)

    # by parent in the order given, each named from its tree and the subject
    assert [child['name'] for child in children] == [
        'Arrival Tree A - Leaf 1', 'Arrival Tree A - Leaf 2', 'Arrival Tree C - Leaf 1', 'Arrival Tree C - Leaf 2'
    ]
    assert [child['parents'] for child in children] == [[{'id': str(tree_a)}]] * 2 + [[{'id': str(tree_c)}]] * 2
    assert {child['subject']['id'] for child in children} == {str(read_policy['ontology_subject_leaf'])}
    # where their trees were that day, which is where their field is, from then
    assert [places(child) for child in children] == [[(read_policy[FIELD], None, None, '2025-05-03', None)]] * 4
    # germplasm of their own none, they take their trees'
    assert {child['germplasm'] for child in children} == {None}
    assert {child['inheritedGermplasm']['germplasm']['id'] for child in children} == {str(read_policy['crop_leaf'])}

    # taken where their trees were, they did not arrive at the field
    payload = await post(client, login_token_factory, writer, ARRIVALS, {
        'locationIds': [read_policy[FIELD]]
    }, 'unitsArrivals')
    assert '2025-05-03' not in [arrival['start'] for arrival in payload['result']]


@pytest.mark.asyncio(loop_scope="session")
async def test_a_parent_is_placed_where_it_was_then(client, login_token_factory, read_policy, arrivals):
    writer = read_policy['writer']
    tree_b = arrivals.units['Arrival Tree B']

    async def taken(start: str) -> list:
        (child,) = await added(client, login_token_factory, writer, {
            'parents': {'unitIds': [tree_b]},
            'subjectId': read_policy['ontology_subject_leaf'],
            'name': f'Tree B leaf of {start}',
            'start': start,
            'controlTeamId': read_policy['child']
        })
        return places(child)

    # Tree B visited the lab in June 2024, then came back to the field
    assert await taken('2024-06-15') == [(read_policy[LAB], None, None, '2024-06-15', None)]
    assert await taken('2024-08-01') == [(read_policy[FIELD], None, None, '2024-08-01', None)]


@pytest.mark.asyncio(loop_scope="session")
async def test_children_of_an_arrival_without_a_start_or_a_name(client, login_token_factory, read_policy, arrivals):
    writer = read_policy['writer']
    # the samples that arrived at the lab on 2025-06-10, an extract of each: where its sample is, unnamed
    children = await added(client, login_token_factory, writer, {
        'parents': {'arrival': {'locationId': read_policy[LAB], 'start': '2025-06-10'}},
        'subjectId': read_policy['ontology_subject_sample'],
        'name': None,
        'controlTeamId': read_policy['child']
    })
    assert sorted(int(child['parents'][0]['id']) for child in children) == sorted([
        arrivals.units['Arrival Move Sample 1'], arrivals.units['Arrival Move Sample 2']
    ])
    assert [(child['name'], child['positions']) for child in children] == [(None, [])] * 2


@pytest.mark.asyncio(loop_scope="session")
async def test_adding_children_refused(client, login_token_factory, read_policy, arrivals):
    writer, stranger = read_policy['writer'], read_policy['stranger']
    pooled, tree_c = arrivals.units['Arrival Pooled'], arrivals.units['Arrival Tree C']
    leaves = {'subjectId': read_policy['ontology_subject_leaf'], 'controlTeamId': read_policy['child']}

    async def child_counts() -> list:
        payload = await post(client, login_token_factory, writer, """
            query ($ids: [ID!]) { unitsUnits(ids: $ids) { status result { children { id } } errors { message } } }
        """, {'ids': [pooled, tree_c]}, 'unitsUnits')
        return [len(unit['children']) for unit in payload['result']]

    before = await child_counts()

    # pooled from Tree A in the field and Tree B at the lab in June 2024: where it was then can't be told
    message = await refused(client, login_token_factory, writer, {
        'parents': {'unitIds': [pooled, tree_c]}, 'start': '2024-06-15', **leaves
    })
    assert 'Where Arrival Pooled was at 2024-06-15 can\'t be told' in message
    # too many, or names that would repeat
    assert 'from 1 to 100' in await refused(client, login_token_factory, writer, {
        'parents': {'unitIds': [tree_c]}, 'count': 101, **leaves
    })
    assert 'needs {n}' in await refused(client, login_token_factory, writer, {
        'parents': {'unitIds': [tree_c]}, 'count': 2, 'name': '{parent} leaf', **leaves
    })
    # a parent the user can't read
    await refused(client, login_token_factory, stranger, {
        'parents': {'unitIds': [read_policy['leaf_private']]},
        'subjectId': read_policy['ontology_subject_sample'],
        'controlTeamId': read_policy['other']
    })

    # nothing was added, not even to Tree C, whose place could be told
    assert await child_counts() == before
