import json
from pathlib import Path
from src.breedgraph.config import GQL_API_PATH
from tests.e2e.utils import with_auth


async def post_to_create_legal_reference(client, token:str, reference):
    json_str = {
        "query": (
            " mutation ( "
            "  $reference: CreateLegalReferenceInput!"
            " ) { "
            "  referencesCreateLegal ( "
            "    reference: $reference "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "reference": reference
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json_str, headers=headers)
    return response


async def post_to_create_file_reference(client, token:str, reference):
    test_file = reference.pop('file')
    filepath = Path(test_file.name)
    operations = {
        "query": """
            mutation StoreFile($reference: CreateFileReferenceInput!) {
                referencesCreateFile(reference: $reference) {
                    status
                    result
                    errors { message }
                }
            }
        """,
        "variables": {
            "reference": {
                **reference,
                "file": None  # Must be null here
            }
        }
    }

    # Maps form field "0" to the nested "file" variable
    map_data = {"0": ["variables.reference.file"]}

    # The 'files' argument in httpx/requests handles the binary part
    files = {
        "0": (filepath.name, test_file, "application/pdf")
    }

    # Use 'data' for the JSON strings of the spec
    data = {
        "operations": json.dumps(operations),
        "map": json.dumps(map_data)
    }

    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, data=data, files=files, headers=headers)
    return response

async def post_to_file_submission(client, token:str, file_id: str):
    json_str = {
        "query": (
            " query ( "
            "  $fileId: String!"
            " ) { "
            "  referencesFileSubmission ( "
            "    fileId: $fileId "
            "  ) { "
            "    status, "
            "    result { "
            "       referenceId, "
            "       status, "
            "       progress, "
            "       errors  "
            "    }, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "fileId": file_id
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json_str, headers=headers)
    return response

async def post_to_file_download(client, token:str, file_id: str):
    json_str = {
        "query": (
            " query ( "
            "  $fileId: String!"
            " ) { "
            "  referencesFileDownload ( "
            "    fileId: $fileId "
            "  ) { "
            "    status, "
            "    result { "
            "       filename "
            "       contentType "
            "       token "
            "       expiresAt "
            "       url "
            "    }, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "fileId": file_id
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json_str, headers=headers)
    return response