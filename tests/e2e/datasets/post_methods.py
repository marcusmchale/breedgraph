from src.breedgraph.config import GQL_API_PATH

async def post_to_add_dataset(client, token:str, term: int):
    json={
        "query": (
            " mutation ( "
            "  $term: Int!"
            " ) { "
            "  data_add_dataset( "
            "    term: $term "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "term": term
        }
    }
    return await client.post(f"{GQL_API_PATH}/", json=json, headers={"token":token})

async def post_to_get_datasets(client, token:str, term: int|None = None):
    json={
        "query": (
            " query ( "
            "  $term: Int!"
            " ) { "
            "  data_get_datasets( "
            "    term: $term "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "term": term
        }
    }
    return await client.post(f"{GQL_API_PATH}/", json=json, headers={"token":token})