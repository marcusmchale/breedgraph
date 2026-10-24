"""
Arrivals through GraphQL, on the arrivals scenario (tests/breedgraph/scenarios/arrival_scenario.py; the view underneath
is tested in tests/breedgraph/integration/views/test_unit_arrivals_view.py): unitsArrivals with each arrival's location,
start as entered, roots and units by subject, and unitsArrivalUnits by an arrival's location and start; with below,
the arrivals and unit graph roots under a location too.
"""
import pytest

from breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus

from tests.breedgraph.e2e.utils import post_as, get_verified_payload
from tests.breedgraph.scenarios.arrival_scenario import EXPECTED_ARRIVALS, LAB, STORE

ARRIVALS = """
query ($locationIds: [ID!]!, $unitId: ID, $below: Boolean) {
  unitsArrivals(locationIds: $locationIds, unitId: $unitId, below: $below) {
    status errors { message }
    result {
      location { id name }
      start
      unitCount
      roots { id name }
      unitsBySubject { subject { id name } units { id name } }
    }
  }
}
"""
ROOTS = """
query ($locationIds: [ID!], $below: Boolean) {
  unitsRoots(locationIds: $locationIds, below: $below) { status errors { message } result { id name } }
}
"""
ARRIVAL_UNITS = """
query ($arrival: ArrivalInput!, $offset: Int, $limit: Int) {
  unitsArrivalUnits(arrival: $arrival, offset: $offset, limit: $limit) {
    status errors { message }
    result { id name parents { id } positions { location { id } start end } }
  }
}
"""


async def query(client, login_token_factory, user_id, operation: str, text: str, variables: dict):
    payload = get_verified_payload(await post_as(client, login_token_factory, user_id, text, variables), operation)
    assert payload['status'] == GQLStatus.SUCCESS.name, payload['errors']
    return payload['result']


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', ['writer', 'outsider', 'anonymous'])
async def test_arrivals_at_the_lab(client, login_token_factory, read_policy, arrivals, viewer):
    user_id = read_policy.user(viewer)
    found = await query(client, login_token_factory, user_id, 'unitsArrivals', ARRIVALS, {'locationIds': [read_policy[LAB]]})
    expected = EXPECTED_ARRIVALS[LAB][viewer]
    assert [arrival['start'] for arrival in found] == [start for start, _ in expected]
    for arrival, (start, names) in zip(found, expected):
        assert arrival['location']['id'] == str(read_policy[LAB])
        assert arrival['unitCount'] == len(names)
        assert [root['id'] for root in arrival['roots']] == [str(arrivals.units['Arrival Field'])]
        listed = sorted(unit['name'] for group in arrival['unitsBySubject'] for unit in group['units'])
        assert listed == sorted(names)
        page = await query(client, login_token_factory, user_id, 'unitsArrivalUnits', ARRIVAL_UNITS, {
            'arrival': {'locationId': read_policy[LAB], 'start': start}
        })
        assert [unit['name'] for unit in page] == names


@pytest.mark.asyncio(loop_scope="session")
async def test_arrival_units_in_pages_and_related_to_a_unit(client, login_token_factory, read_policy, arrivals):
    writer, lab = read_policy['writer'], read_policy[LAB]
    first = await query(client, login_token_factory, writer, 'unitsArrivalUnits', ARRIVAL_UNITS, {
        'arrival': {'locationId': lab, 'start': '2025-03-25'}, 'limit': 2
    })
    rest = await query(client, login_token_factory, writer, 'unitsArrivalUnits', ARRIVAL_UNITS, {
        'arrival': {'locationId': lab, 'start': '2025-03-25'}, 'offset': 2, 'limit': 100
    })
    assert [unit['name'] for unit in first + rest] == dict(EXPECTED_ARRIVALS[LAB]['writer'])['2025-03-25']
    from_tree_b = await query(client, login_token_factory, writer, 'unitsArrivals', ARRIVALS, {
        'locationIds': [lab], 'unitId': arrivals.units['Arrival Tree B']
    })
    # Tree B's own visit, and the arrival of its sample and the sample pooled from it
    assert [(a['start'], a['unitCount']) for a in from_tree_b] == [('2025-03-25', 2), ('2024-06', 1)]
    moved_on = await query(client, login_token_factory, writer, 'unitsArrivals', ARRIVALS, {
        'locationIds': [arrivals.ids[STORE]]
    })
    assert [(a['start'], a['location']['name']) for a in moved_on] == [('2025-05-02', 'Arrival Lab Store')]


@pytest.mark.asyncio(loop_scope="session")
async def test_arrivals_and_roots_below_a_location(client, login_token_factory, read_policy, arrivals):
    """
    With below, a field's arrivals are those of the centre, lab and store under it, each at the location it came to,
    and a country's unit graph roots are those of the locations under it
    """
    writer = read_policy['writer']
    below = await query(client, login_token_factory, writer, 'unitsArrivals', ARRIVALS, {
        'locationIds': [read_policy['field']], 'below': True
    })
    each = []
    for location_id in (read_policy['field'], read_policy['centre'], read_policy[LAB], arrivals.ids[STORE]):
        each += await query(client, login_token_factory, writer, 'unitsArrivals', ARRIVALS, {'locationIds': [location_id]})
    key = lambda arrival: (arrival['location']['id'], arrival['start'] or '', arrival['unitCount'])
    assert sorted(map(key, below)) == sorted(map(key, each))
    assert {arrival['location']['name'] for arrival in below} >= {'Arrival Lab Store'}

    roots_below = await query(client, login_token_factory, writer, 'unitsRoots', ROOTS, {
        'locationIds': [read_policy['country']], 'below': True
    })
    at_field = await query(client, login_token_factory, writer, 'unitsRoots', ROOTS, {'locationIds': [read_policy['field']]})
    at_country = await query(client, login_token_factory, writer, 'unitsRoots', ROOTS, {'locationIds': [read_policy['country']]})
    assert at_field and {root['id'] for root in at_field} <= {root['id'] for root in roots_below}
    assert {root['id'] for root in at_country} < {root['id'] for root in roots_below}
