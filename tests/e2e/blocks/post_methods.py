from src.breedgraph.config import GQL_API_PATH
from tests.e2e.utils import with_auth

async def post_to_create_unit(client, token:str, unit: dict):
    json={
        "query": (
            " mutation ( "
            "  $unit: UnitInput!"
            " ) { "
            "  blocksCreateUnit( "
            "    unit: $unit "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "unit": unit
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
            "  $position: PositionInput"
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


async def post_to_blocks(client, token:str, location_id: int = None):
    json={
        "query": (
            " query ( "
            "  $locationId: Int"
            " ) { "
            "  blocks( "
            "    locationId: $locationId "
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
            "locationId": location_id
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response

async def post_to_unit(client, unit_id: int, token:str = None):
    json = {
        "query": (
            " query ("
            "   $unitId : Int!"
            " ) { "
            "  blocksUnit ( "
            "  unitId: $unitId,"
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
            "unitId": unit_id,
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response

