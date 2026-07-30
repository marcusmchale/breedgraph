from breedgraph.config import GQL_API_PATH
from tests.breedgraph.e2e.utils import with_auth

from typing import List

async def post_to_create_unit(client, token:str, unit: dict, control_team_id: int, position: dict|None = None):
    json={
        "query": (
            " mutation ( "
            "  $unit: UnitInput! "
            "  $position: PositionInput "
            "  $controlTeamId: ID! "
            " ) { "
            "  blocksCreateUnit( "
            "    unit: $unit "
            "    position: $position "
            "    controlTeamId: $controlTeamId "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "unit": unit,
            "position": position,
            "controlTeamId": control_team_id
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
            "  $id: ID! "
            "  $position: PositionInput! "
            " ) { "
            "  blocksAddPosition( "
            "    id: $id "
            "    position: $position "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "id": unit_id,
            "position": position
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response


async def post_to_blocks(client, token:str, location_ids: List[int]|None = None):
    json={
        "query": (
            " query ( "
            "  $locationIds: [ID!]"
            " ) { "
            "  blocks( "
            "    locationIds: $locationIds "
            "  ) { "
            "    status, "
            "    result { "
            "       id, name, "
            "       subject { id, name }"
            "       children {"
            "           id, "
            "           subject { id, name },"
            "           children { id, name } "
            "       } "
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
            "   $ids : [ID!]"
            " ) { "
            "  blocksUnits ( "
            "  ids: $ids,"
            "  ) {"
            "    status, "
            "    result { "
            "       id, name, "
            "       subject { id, name }"
            "       parents {id, name, subject {id, name} } "
            "       children {id, name, subject {id, name} } "
            "    }, "
            "    errors { name, message } "
            "   } "
            " } "
        ),
        "variables": {
            "ids": unit_ids,
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response

