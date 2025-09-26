from src.breedgraph.config import GQL_API_PATH
from tests.e2e.utils import with_auth

async def post_to_create_dataset(client, token:str, concept_id: int):
    json={
        "query": (
            " mutation ( "
            "  $conceptId: Int!"
            " ) { "
            "  datasetsCreateDataset( "
            "    conceptId: $conceptId "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "conceptId": concept_id
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response


async def post_to_add_record(client, token:str, record: dict):
    json={
        "query": (
            " mutation ( "
            "  $record: RecordInput!"
            " ) { "
            "  datasetsAddRecord( "
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
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response

async def post_to_get_datasets(client, token:str, dataset_id: int|None = None, concept_id: int|None = None):
    json={
        "query": (
            " query ( "
            "  $datasetId: Int"
            "  $conceptId: Int"
            " ) { "
            "  datasets( "
            "    datasetId: $datasetId "
            "    conceptId: $conceptId "
            "  ) { "
            "    status, "
            "    result { "
            "       id, "
            "       concept {id, name, description},"
            "       records { unit {id} } "
            "   } "
            "   errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "datasetId": dataset_id,
            "conceptId": concept_id

        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response