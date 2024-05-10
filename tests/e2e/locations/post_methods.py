from src.breedgraph.config import GQL_API_PATH

async def post_to_countries(client, token:str):
    json = {
        "query": (
            " query { "
            "  countries { "
            "    status, "
            "    result { "
            "       name, "
            "       code "  
            "    }, "
            "    errors { name, message } "
            "   } "
            " } "
        )
    }
    return await client.post(f"{GQL_API_PATH}/", json=json, headers={"token":token})

async def post_to_add_country(client, token:str, name: str, code: str):
    json = {
        "query": (
            " mutation ( "
            "  $name: String!,"
            "  $code: String"
            " ) { "
            "  add_country( "
            "    name: $name, "
            "    code: $code"
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "name": f"{name}",
            "code": f"{code}"
        }
    }
    return await client.post(f"{GQL_API_PATH}/", json=json, headers={"token":token})