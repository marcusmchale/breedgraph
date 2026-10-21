"""
Moving units and changing their positions through GraphQL, written outside the unit graph (application.unit_positions),
on the arrivals scenario's spare units (tests/breedgraph/scenarios/arrival_scenario.py): Arrival Move Sample 1 and 2,
at the lab from 2025-06-10. An arrival moved on to the lab store, ended there and its start corrected, each a write of
the whole arrival; a move before a later position refused; unitsAddPosition and unitsRemovePosition on one unit; and
the refusals, which change nothing: curate access to every unit, the selection, the destination, a position to change.
"""
import pytest

from breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus

from tests.breedgraph.e2e.utils import post_as, get_verified_payload
from tests.breedgraph.scenarios.arrival_scenario import LAB, STORE, FIELD

UNIT_POSITIONS = "result { id name positions { location { id } layout { id } start end } }"
MOVE = f"""
mutation ($units: UnitsSelection!, $position: PositionInput!) {{
  unitsMoveUnits(units: $units, position: $position) {{ status errors {{ name message }} {UNIT_POSITIONS} }}
}}
"""
CHANGE = f"""
mutation ($units: UnitsSelection!, $at: PositionMatchInput!, $change: PositionChangeInput!) {{
  unitsChangePositions(units: $units, at: $at, change: $change) {{ status errors {{ name message }} {UNIT_POSITIONS} }}
}}
"""
ADD = """
mutation ($id: ID!, $position: PositionInput!) {
  unitsAddPosition(id: $id, position: $position) { status errors { name message } }
}
"""
REMOVE = """
mutation ($id: ID!, $position: PositionInput!) {
  unitsRemovePosition(id: $id, position: $position) { status errors { name message } }
}
"""
UNITS = f"""
query ($ids: [ID!]) {{ unitsUnits(ids: $ids) {{ status errors {{ name message }} {UNIT_POSITIONS} }} }}
"""
ARRIVALS = """
query ($ids: [ID!]!) { unitsArrivals(locationIds: $ids) { status result { start unitCount } errors { message } } }
"""
SAMPLES = ['Arrival Move Sample 1', 'Arrival Move Sample 2']


async def send(client, login_token_factory, user_id, text: str, operation: str, variables: dict) -> dict:
    return get_verified_payload(await post_as(client, login_token_factory, user_id, text, variables), operation)


def succeeded(payload: dict):
    assert payload['status'] == GQLStatus.SUCCESS.name, payload['errors']
    return payload.get('result')


def refused(payload: dict, name: str, message: str):
    assert payload['status'] == GQLStatus.ERROR.name, payload
    (error,) = payload['errors']
    assert error['name'] == name and message in error['message'], error


def positions(unit: dict) -> list:
    return [(int(p['location']['id']), p['start'], p['end']) for p in unit['positions']]


@pytest.fixture
def ids(read_policy, arrivals):
    return {
        LAB: read_policy[LAB], STORE: arrivals.ids[STORE], FIELD: read_policy[FIELD],
        **{name: arrivals.units[name] for name in SAMPLES + ['Arrival Field']}
    }


def lab_arrival(ids, start='2025-06-10') -> dict:
    return {'arrival': {'locationId': ids[LAB], 'start': start}}


@pytest.mark.asyncio(loop_scope="session")
async def test_curate_access_to_every_unit_is_needed(client, login_token_factory, read_policy, ids):
    # the outsider reads the samples, and so finds the arrival, but curates none of them
    payload = await send(client, login_token_factory, read_policy['outsider'], MOVE, 'unitsMoveUnits', {
        'units': lab_arrival(ids), 'position': {'locationId': ids[STORE], 'start': '2025-07-01'}
    })
    refused(payload, 'UnauthorisedOperationError',
            'Changing the positions of Arrival Move Sample 1 and Arrival Move Sample 2 requires curate access')
    payload = await send(client, login_token_factory, None, MOVE, 'unitsMoveUnits', {
        'units': lab_arrival(ids), 'position': {'locationId': ids[STORE], 'start': '2025-07-01'}
    })
    refused(payload, 'UnauthorisedOperationError', 'Please provide a valid token')


@pytest.mark.asyncio(loop_scope="session")
async def test_the_selection_and_destination_are_checked(client, login_token_factory, read_policy, ids):
    writer = read_policy['writer']
    both = {'unitIds': [ids['Arrival Move Sample 1']], **lab_arrival(ids)}
    for units in (both, {}):
        payload = await send(client, login_token_factory, writer, MOVE, 'unitsMoveUnits', {
            'units': units, 'position': {'locationId': ids[STORE], 'start': '2025-07-01'}
        })
        refused(payload, 'ValueError', 'Give the units by id or by arrival')
    payload = await send(client, login_token_factory, writer, MOVE, 'unitsMoveUnits', {
        'units': lab_arrival(ids, '2025-06'), 'position': {'locationId': ids[STORE], 'start': '2025-07-01'}
    })
    refused(payload, 'NoResultFoundError', 'No units you can read arrived there then')
    payload = await send(client, login_token_factory, writer, MOVE, 'unitsMoveUnits', {
        'units': lab_arrival(ids), 'position': {'locationId': ids[STORE]}
    })
    refused(payload, 'ValueError', 'A move needs a start')
    # the layout is at the field
    payload = await send(client, login_token_factory, writer, MOVE, 'unitsMoveUnits', {
        'units': lab_arrival(ids),
        'position': {'locationId': ids[LAB], 'layoutId': read_policy['facility'], 'coordinates': ['1'], 'start': '2025-07-01'}
    })
    refused(payload, 'ValueError', 'Layout location does not match the position location')
    payload = await send(client, login_token_factory, writer, CHANGE, 'unitsChangePositions', {
        'units': lab_arrival(ids), 'at': {'locationId': ids[FIELD]}, 'change': {'end': '2025-07-01'}
    })
    refused(payload, 'NoResultFoundError', 'No position matching the details given was found for Arrival Move Sample 1')
    # nothing changed
    units = succeeded(await send(client, login_token_factory, writer, UNITS, 'unitsUnits', {
        'ids': [ids[name] for name in SAMPLES]
    }))
    assert [positions(unit) for unit in units] == [[(ids[LAB], '2025-06-10', None)]] * 2


@pytest.mark.asyncio(loop_scope="session")
async def test_an_arrival_moved_on_ended_and_corrected(client, login_token_factory, read_policy, ids):
    writer = read_policy['writer']
    moved = succeeded(await send(client, login_token_factory, writer, MOVE, 'unitsMoveUnits', {
        'units': lab_arrival(ids), 'position': {'locationId': ids[STORE], 'start': '2025-07-01'}
    }))
    assert [unit['name'] for unit in moved] == SAMPLES
    assert [positions(unit) for unit in moved] == [
        [(ids[LAB], '2025-06-10', '2025-07-01'), (ids[STORE], '2025-07-01', None)]
    ] * 2
    arrivals = succeeded(await send(client, login_token_factory, writer, ARRIVALS, 'unitsArrivals', {'ids': [ids[STORE]]}))
    assert [(a['start'], a['unitCount']) for a in arrivals] == [('2025-07-01', 2), ('2025-05-02', 1)]

    store_arrival = {'arrival': {'locationId': ids[STORE], 'start': '2025-07-01'}}
    ended = succeeded(await send(client, login_token_factory, writer, CHANGE, 'unitsChangePositions', {
        'units': store_arrival, 'at': {'locationId': ids[STORE], 'start': '2025-07-01'}, 'change': {'end': '2025-08'}
    }))
    assert [positions(unit)[-1] for unit in ended] == [(ids[STORE], '2025-07-01', '2025-08')] * 2

    corrected = succeeded(await send(client, login_token_factory, writer, CHANGE, 'unitsChangePositions', {
        'units': store_arrival, 'at': {'locationId': ids[STORE], 'start': '2025-07-01'}, 'change': {'start': '2025-07-02'}
    }))
    assert [positions(unit) for unit in corrected] == [
        [(ids[LAB], '2025-06-10', '2025-07-01'), (ids[STORE], '2025-07-02', '2025-08')]
    ] * 2
    arrivals = succeeded(await send(client, login_token_factory, writer, ARRIVALS, 'unitsArrivals', {'ids': [ids[STORE]]}))
    assert [(a['start'], a['unitCount']) for a in arrivals] == [('2025-07-02', 2), ('2025-05-02', 1)]

    # back to the field, but not before their time in the store
    payload = await send(client, login_token_factory, writer, MOVE, 'unitsMoveUnits', {
        'units': {'unitIds': [ids['Arrival Move Sample 1']]}, 'position': {'locationId': ids[FIELD], 'start': '2025-07-01'}
    })
    refused(payload, 'IllegalOperationError', 'Arrival Move Sample 1 has a position from 2025-07-01 or later')


@pytest.mark.asyncio(loop_scope="session")
async def test_a_position_added_and_removed_on_one_unit(client, login_token_factory, read_policy, ids):
    writer, sample = read_policy['writer'], ids['Arrival Move Sample 2']
    position = {'locationId': ids[FIELD], 'start': '2025-09'}
    succeeded(await send(client, login_token_factory, writer, ADD, 'unitsAddPosition', {'id': sample, 'position': position}))
    refused(await send(client, login_token_factory, writer, ADD, 'unitsAddPosition', {'id': sample, 'position': position}),
            'ValueError', 'The unit already has this position')
    unit, = succeeded(await send(client, login_token_factory, writer, UNITS, 'unitsUnits', {'ids': [sample]}))
    assert positions(unit)[-1] == (ids[FIELD], '2025-09', None)
    # matched as entered: another precision is another position
    refused(await send(client, login_token_factory, writer, REMOVE, 'unitsRemovePosition', {
        'id': sample, 'position': {'locationId': ids[FIELD], 'start': '2025-09-01'}
    }), 'ValueError', 'was not found')
    succeeded(await send(client, login_token_factory, writer, REMOVE, 'unitsRemovePosition', {'id': sample, 'position': position}))
    unit, = succeeded(await send(client, login_token_factory, writer, UNITS, 'unitsUnits', {'ids': [sample]}))
    assert (ids[FIELD], '2025-09', None) not in positions(unit)
    # a unit graph's root keeps its last position
    root, = succeeded(await send(client, login_token_factory, writer, UNITS, 'unitsUnits', {'ids': [ids['Arrival Field']]}))
    (last,) = root['positions']
    refused(await send(client, login_token_factory, writer, REMOVE, 'unitsRemovePosition', {
        'id': ids['Arrival Field'], 'position': {'locationId': last['location']['id'], 'start': last['start'], 'end': last['end']}
    }), 'IllegalOperationError', 'at least one position')
