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


async def post_to_add_record(client, token:str, record: dict):
    json={
        "query": (
            " mutation ( "
            "  $record: RecordInput!"
            " ) { "
            "  data_add_record( "
            "    record: $record "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "record": record
        }
    }
    return await client.post(f"{GQL_API_PATH}/", json=json, headers={"token":token})

async def post_to_get_datasets(client, token:str, dataset_id: int|None = None, term_id: int|None = None):
    json={
        "query": (
            " query ( "
            "  $dataset_id: Int"
            "  $term_id: Int"
            " ) { "
            "  datasets( "
            "    dataset_id: $dataset_id "
            "    term_id: $term_id "
            "  ) { "
            "    status, "
            "    result { "
            "       id, "
            "       term {id},"
            "       records { unit {id} } "
            "   } "
            "   errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "dataset_id": dataset_id,
            "term_id": term_id

        }
    }
    return await client.post(f"{GQL_API_PATH}/", json=json, headers={"token":token})