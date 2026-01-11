from src.breedgraph.config import GQL_API_PATH
from tests.e2e.utils import with_auth

from typing import List

async def post_to_create_unit(client, token:str, unit: dict, position: dict|None = None):
    json={
        "query": (
            " mutation ( "
            "  $unit: UnitInput! "
            "  $position: PositionInput "
            " ) { "
            "  blocksCreateUnit( "
            "    unit: $unit "
            "    position: $position "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "unit": unit,
            "position": position
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response

async def post_to_add_position(client, token:str, unit_id: int, position: dict):
    json={
        "query": (
            " mutation ( "
            "  $unitId: Int! "
            "  $position: PositionInput! "
            " ) { "
            "  blocksAddPosition( "
            "    unitId: $unitId "
            "    position: $position "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "unitId": unit_id,
            "position": position
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response


async def post_to_blocks(client, token:str, location_ids: List[int] = None):
    json={
        "query": (
            " query ( "
            "  $locationIds: [Int!]"
            " ) { "
            "  blocks( "
            "    locationIds: $locationIds "
            "  ) { "
            "    status, "
            "    result { "
            "       id, "
            "       subject { id, name }"
            "       parents {id, subject { id, name } } "
            "       children {id, subject { id, name } } "
            "    } "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "locationIds": location_ids or []
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response

async def post_to_units(client, unit_ids: List[int], token:str = None):
    json = {
        "query": (
            " query ("
            "   $unitIds : [Int!]"
            " ) { "
            "  blocksUnits ( "
            "  unitIds: $unitIds,"
            "  ) {"
            "    status, "
            "    result { "
            "       id, "
            "       name, "
            "       subject { id, name }"
            "       parents {id, name, subject {id, name} } "
            "       children {id, name, subject {id, name} } "
            "    }, "
            "    errors { name, message } "
            "   } "
            " } "
        ),
        "variables": {
            "unitIds": unit_ids,
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response

