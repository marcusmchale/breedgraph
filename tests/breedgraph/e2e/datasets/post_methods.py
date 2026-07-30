from breedgraph.config import GQL_API_PATH
from tests.breedgraph.e2e.utils import with_auth


async def post_to_create_dataset(client, token:str, dataset: dict, control_team_id: int):
    json={
        "query": (
            " mutation ( "
            "  $dataset: DatasetInput!"
            "  $controlTeamId: ID! "
            " ) { "
            "  datasetsCreate( "
            "    dataset: $dataset "
            "    controlTeamId: $controlTeamId "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "dataset": dataset,
            "controlTeamId": control_team_id
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
            "  datasetsUpdate( "
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
            "  $id: ID"
            "  $conceptId: ID"
            " ) { "
            "  datasets( "
            "    id: $id "
            "    conceptId: $conceptId "
            "  ) { "
            "    status, "
            "    result { "
            "       id, "
            "       concept { id, name, description },"
            "       records { unit {id} } "
            "   } "
            "   errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "id": dataset_id,
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
            "  $id: ID!"
            " ) { "
            "  datasetsSubmission( "
            "    id: $id "
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
            "id": submission_id

        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response