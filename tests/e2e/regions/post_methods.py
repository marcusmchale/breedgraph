from src.breedgraph.config import GQL_API_PATH

async def post_to_countries(client, token:str):
    json = {
        "query": (
            " query { "
            "  countries { "
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
    return await client.post(f"{GQL_API_PATH}/", json=json, headers={"token":token})

async def post_to_add_location(
    client,
    token:str,
    location: dict
):
    json = {
        "query": (
            " mutation ( "
            "  $location: LocationInput!"
            " ) { "
            "  add_location( "
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
    return await client.post(f"{GQL_API_PATH}/", json=json, headers={"token":token})

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
            "       release "
            "    }, "
            "    errors { name, message } "
            "   } "
            " } "
        )
    }
    if token:
        headers={"token":token}
    else:
        headers=None
    return await client.post(f"{GQL_API_PATH}/", json=json, headers=headers)

async def post_to_location(client, location_id: int, token:str = None):
    json = {
        "query": (
            " query ("
            "   $location_id : Int!"
            " ) { "
            "  location ( "
            "  location_id: $location_id,"
            "  ) {"
            "    status, "
            "    result { "
            "       id, "
            "       name, "
            "       code, "  
            "       type { id, name }"
            "       parent {id, name, code, type {id, name} } "
            "       children {id, name, code, type {id, name} } "
            "       release "
            "    }, "
            "    errors { name, message } "
            "   } "
            " } "
        ),
        "variables": {
            "location_id": location_id,
        }
    }
    if token:
        headers={"token":token}
    else:
        headers=None
    return await client.post(f"{GQL_API_PATH}/", json=json, headers=headers)
