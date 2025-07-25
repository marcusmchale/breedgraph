from src.breedgraph.config import GQL_API_PATH
from tests.e2e.utils import with_auth

async def post_to_add_unit(client, token:str, unit: dict):
    json={
        "query": (
            " mutation ( "
            "  $unit: UnitInput!"
            " ) { "
            "  blocks_add_unit( "
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
            "  $unit_id: Int! "
            "  $position: PositionInput"
            " ) { "
            "  blocks_add_position( "
            "    unit_id: $unit_id "
            "    position: $position "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "unit_id": unit_id,
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
            "  $location_id: Int"
            " ) { "
            "  blocks( "
            "    location_id: $location_id "
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
            "location_id": location_id
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
            "   $unit_id : Int!"
            " ) { "
            "  unit ( "
            "  unit_id: $unit_id,"
            "  ) {"
            "    status, "
            "    result { "
            "       id, "
            "       name, "
            "       subject { id, name }"
            "       parents {id, name, subject {id, name} } "
            "       children {id, name, subject {id, name} } "
            "       release "
            "    }, "
            "    errors { name, message } "
            "   } "
            " } "
        ),
        "variables": {
            "unit_id": unit_id,
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response

