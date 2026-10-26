"""
Placing units, each at a position of its own, through GraphQL (unitsPlaceUnits), on the positions scenario's field
laid out in blocks (tests/breedgraph/scenarios/position_scenario.py), which this module builds for itself: South Tree
1-1 and 1-2 in Block 1, South Tree 2-1 in Block 2, each without a start. The refusals first, which change nothing,
whichever placement is at fault; then the trees placed and given germplasm, a tree already at its place left as it is,
germplasm removed, and a placement before a tree's latest position refused.
"""
import pytest

from breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus

from tests.breedgraph.e2e.utils import post_as, get_verified_payload
from tests.breedgraph.scenarios.position_scenario import SOUTH, SOUTH_BLOCK_1, SOUTH_BLOCK_2

UNIT_FIELDS = "result { id name germplasm { id } positions { location { id } layout { id } coordinates start end } }"
PLACE = f"""
mutation ($placements: [UnitPlacementInput!]!) {{
  unitsPlaceUnits(placements: $placements) {{ status errors {{ name message }} {UNIT_FIELDS} }}
}}
"""
UNITS = f"query ($ids: [ID!]) {{ unitsUnits(ids: $ids) {{ status errors {{ name message }} {UNIT_FIELDS} }} }}"
TREES = ['South Tree 1-1', 'South Tree 1-2', 'South Tree 2-1']
PLANTED = '2026-10-15'


async def send(client, login_token_factory, user_id, text: str, operation: str, variables: dict) -> dict:
    return get_verified_payload(await post_as(client, login_token_factory, user_id, text, variables), operation)


def succeeded(payload: dict):
    assert payload['status'] == GQLStatus.SUCCESS.name, payload['errors']
    return payload.get('result')


def refused(payload: dict, name: str, message: str):
    assert payload['status'] == GQLStatus.ERROR.name, payload
    (error,) = payload['errors']
    assert error['name'] == name and message in error['message'], error


@pytest.fixture
def ids(read_policy, positions):
    return {
        SOUTH: positions.locations[SOUTH], SOUTH_BLOCK_1: positions.layouts[SOUTH_BLOCK_1],
        SOUTH_BLOCK_2: positions.layouts[SOUTH_BLOCK_2], **{tree: positions.units[tree] for tree in TREES}
    }


def placement(ids, tree: str, block: str | None = None, coordinates=(), start=PLANTED, **values) -> dict:
    if block is None:
        return {'unitId': ids[tree], **values}
    position = {'locationId': ids[SOUTH], 'layoutId': ids[block], 'coordinates': list(coordinates), 'start': start}
    return {'unitId': ids[tree], 'position': position, **values}


def where(unit: dict) -> list:
    return [
        (int(p['layout']['id']) if p['layout'] else None, p['coordinates'], p['start'], p['end'])
        for p in unit['positions']
    ]


async def trees(client, login_token_factory, read_policy, ids) -> dict:
    units = succeeded(await send(client, login_token_factory, read_policy['writer'], UNITS, 'unitsUnits', {
        'ids': [ids[tree] for tree in TREES]
    }))
    return {unit['name']: unit for unit in units}


@pytest.mark.asyncio(loop_scope="session")
async def test_refusals_change_nothing(client, login_token_factory, read_policy, ids):
    writer = read_policy['writer']
    before = await trees(client, login_token_factory, read_policy, ids)
    good = placement(ids, 'South Tree 1-1', SOUTH_BLOCK_2, ['2', '1'], germplasmId=read_policy['crop_line'])
    cases = [
        ([], 'ValueError', 'Give the units to place'),
        ([good, placement(ids, 'South Tree 1-1', SOUTH_BLOCK_1, ['5', '1'])], 'ValueError', 'Give each unit once'),
        # a position, whichever placement is at fault
        ([good, placement(ids, 'South Tree 2-1', SOUTH_BLOCK_1, ['3'])], 'ValueError',
         'Coordinates must match the length of specified layout axes'),
        ([good, placement(ids, 'South Tree 2-1', SOUTH_BLOCK_1, ['3', '1'], start=None)], 'ValueError', 'A move needs a start'),
        # germplasm the writer can't read, after the positions
        ([good, placement(ids, 'South Tree 2-1', germplasmId=read_policy['crop_other'])], 'NoResultFoundError',
         f"Germplasm {read_policy['crop_other']} was not found"),
    ]
    for placements, name, message in cases:
        payload = await send(client, login_token_factory, writer, PLACE, 'unitsPlaceUnits', {'placements': placements})
        refused(payload, name, message)
    # the outsider reads the trees, but curates none of them
    payload = await send(client, login_token_factory, read_policy['outsider'], PLACE, 'unitsPlaceUnits', {'placements': [good]})
    refused(payload, 'UnauthorisedOperationError', 'Changing the positions of South Tree 1-1 requires curate access')
    payload = await send(client, login_token_factory, read_policy['outsider'], PLACE, 'unitsPlaceUnits', {
        'placements': [placement(ids, 'South Tree 1-1', germplasmId=read_policy['crop_line'])]
    })
    refused(payload, 'UnauthorisedOperationError', '')
    assert await trees(client, login_token_factory, read_policy, ids) == before


@pytest.mark.asyncio(loop_scope="session")
async def test_each_unit_is_placed_at_its_own_position_with_its_germplasm(client, login_token_factory, read_policy, ids):
    writer = read_policy['writer']
    placed = succeeded(await send(client, login_token_factory, writer, PLACE, 'unitsPlaceUnits', {'placements': [
        placement(ids, 'South Tree 2-1', SOUTH_BLOCK_1, ['3', '1'], germplasmId=read_policy['crop_line']),
        placement(ids, 'South Tree 1-1', SOUTH_BLOCK_2, ['2', '1']),
        # where it is already
        placement(ids, 'South Tree 1-2', SOUTH_BLOCK_1, ['1', '2'], germplasmId=read_policy['crop_line_public']),
    ]}))
    # in the order given
    assert [unit['name'] for unit in placed] == ['South Tree 2-1', 'South Tree 1-1', 'South Tree 1-2']
    units = {unit['name']: unit for unit in placed}
    block_1, block_2 = ids[SOUTH_BLOCK_1], ids[SOUTH_BLOCK_2]
    assert where(units['South Tree 2-1']) == [(block_2, ['1', '1'], None, PLANTED), (block_1, ['3', '1'], PLANTED, None)]
    assert where(units['South Tree 1-1']) == [(block_1, ['1', '1'], None, PLANTED), (block_2, ['2', '1'], PLANTED, None)]
    assert where(units['South Tree 1-2']) == [(block_1, ['1', '2'], None, None)]
    assert int(units['South Tree 2-1']['germplasm']['id']) == read_policy['crop_line']
    assert units['South Tree 1-1']['germplasm'] is None
    assert int(units['South Tree 1-2']['germplasm']['id']) == read_policy['crop_line_public']

    # again, as a table saved twice: nothing changes, and germplasm given as null is removed
    again = succeeded(await send(client, login_token_factory, writer, PLACE, 'unitsPlaceUnits', {'placements': [
        placement(ids, 'South Tree 2-1', SOUTH_BLOCK_1, ['3', '1'], germplasmId=None),
        placement(ids, 'South Tree 1-1', SOUTH_BLOCK_2, ['2', '1']),
    ]}))
    units = {unit['name']: unit for unit in again}
    assert where(units['South Tree 2-1']) == [(block_2, ['1', '1'], None, PLANTED), (block_1, ['3', '1'], PLANTED, None)]
    assert where(units['South Tree 1-1']) == [(block_1, ['1', '1'], None, PLANTED), (block_2, ['2', '1'], PLANTED, None)]
    assert units['South Tree 2-1']['germplasm'] is None

    # placed from before where they are now, their histories would be out of order
    payload = await send(client, login_token_factory, writer, PLACE, 'unitsPlaceUnits', {'placements': [
        placement(ids, 'South Tree 1-2', SOUTH_BLOCK_1, ['4', '1'], start='2026-10-01'),
        placement(ids, 'South Tree 2-1', SOUTH_BLOCK_1, ['4', '2'], start='2026-10-01'),
    ]})
    refused(payload, 'IllegalOperationError', 'South Tree 2-1 has a position from when it is placed or later')
