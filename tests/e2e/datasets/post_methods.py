from src.breedgraph.config import GQL_API_PATH
from tests.e2e.utils import with_auth
from typing import List

async def post_to_create_dataset(client, token:str, dataset: dict):
    json={
        "query": (
            " mutation ( "
            "  $dataset: DatasetInput!"
            " ) { "
            "  datasetsCreateDataset( "
            "    dataset: $dataset "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "dataset": dataset
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response



async def post_to_add_records(client, token:str, dataset_id: int, records: List[dict]):
    json={
        "query": (
            " mutation ( "
            "  $datasetId: Int! "
            "  $records: [RecordInput!]!"
            " ) { "
            "  datasetsAddRecords( "
            "    datasetId: $datasetId "
            "    records: $records "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "datasetId": dataset_id,
            "records": records
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response

async def post_to_update_dataset(client, token:str, dataset:dict):
    json={
        "query": (
            " mutation ( "
            "  $dataset: DatasetUpdate!"
            " ) { "
            "  datasetsUpdateDataset( "
            "    dataset: $dataset "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "dataset": dataset
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



async def post_to_get_dataset_submission(client, token:str, submission_id: str):
    json={
        "query": (
            " query ( "
            "  $submissionId: String!"
            " ) { "
            "  datasetsSubmission( "
            "    submissionId: $submissionId "
            "  ) { "
            "    status, "
            "    result { "
            "       status,"
            "       errors,"
            "       itemErrors { index, error } "
            "    }, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "submissionId": submission_id

        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response