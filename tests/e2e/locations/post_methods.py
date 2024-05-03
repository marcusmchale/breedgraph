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