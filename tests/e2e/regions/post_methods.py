from src.breedgraph.config import GQL_API_PATH
from tests.e2e.utils import with_auth
from typing import List

async def post_to_countries(client, token:str):
    json = {
        "query": (
            " query { "
            "  regionsCountries { "
            "    status, "
            "    result { "
            "       name, "
            "       code, "  
            "       type { id, name }"
            "    }, "
            "    errors { name, message } "
            "   } "
            " } "
        )
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response

async def post_to_create_location(
    client,
    token:str,
    location: dict
):
    json = {
        "query": (
            " mutation ( "
            "  $location: LocationInput!"
            " ) { "
            "  regionsCreateLocation( "
            "    location: $location, "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "location": location
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response

async def post_to_regions(client, token:str):
    json = {
        "query": (
            " query { "
            "  regions { "
            "    status, "
            "    result { "
            "       id, "
            "       name, "
            "       code, "  
            "       type { id, name } "
            "       parent {id, name, code, type {id, name} } "
            "       children {id, name, code, type {id, name} } "
            "    }, "
            "    errors { name, message } "
            "   } "
            " } "
        )
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response

async def post_to_locations(client, location_ids: List[int]|None=None,  location_type_id: int|None=None, token:str = None):
    json = {
        "query": (
            " query ("
            "   $locationIds : [Int!]"
            "   $locationTypeId : Int "
            " ) { "
            "  regionsLocations ( "
            "    locationIds: $locationIds,"
            "    locationTypeId: $locationTypeId "
            "  ) {"
            "    status, "
            "    result { "
            "       id, "
            "       name, "
            "       code, "  
            "       type { id, name }"
            "       parent {id, name, code, type {id, name} } "
            "       children {id, name, code, type {id, name} } "
            "    }, "
            "    errors { name, message } "
            "   } "
            " } "
        ),
        "variables": {
            "locationIds": location_ids,
            "locationTypeId": location_type_id
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response