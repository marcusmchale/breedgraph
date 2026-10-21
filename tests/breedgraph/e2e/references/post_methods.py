import json
from pathlib import Path
from breedgraph.config import GQL_API_PATH
from tests.breedgraph.e2e.utils import with_auth


async def post_to_create_legal_reference(client, token:str, reference, control_team_id: int):
    json_str = {
        "query": (
            " mutation ( "
            "  $reference: LegalReferenceInput! "
            "  $controlTeamId: ID! "
            " ) { "
            "  referencesCreateLegal ( "
            "    reference: $reference "
            "    controlTeamId: $controlTeamId "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "reference": reference,
            "controlTeamId": control_team_id
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json_str, headers=headers)
    return response


async def post_to_create_file_reference(client, token:str, reference, control_team_id: int):
    test_file = reference.pop('file')
    filepath = Path(test_file.name)
    operations = {
        "query": """
            mutation StoreFile(
                $reference: FileReferenceInput!
                $controlTeamId: ID! 
            ) {
                referencesCreateFile(
                  reference: $reference
                  controlTeamId: $controlTeamId
                ) {
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
            },
            "controlTeamId": control_team_id
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

async def post_to_update_file_reference(client, token:str, reference):
    test_file = reference.pop('file')
    filepath = Path(test_file.name)
    operations = {
        "query": """
            mutation UpdateFile(
                $reference: FileReferenceUpdate!
            ) {
                referencesUpdateFile(
                  reference: $reference
                ) {
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
    map_data = {"0": ["variables.reference.file"]}
    files = {
        "0": (filepath.name, test_file, "application/pdf")
    }
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
            "  $fileId: ID!"
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
            "  $fileId: ID!"
            " ) { "
            "  referencesFileDownload ( "
            "    fileId: $fileId "
            "  ) { "
            "    status, "
            "    result { "
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

async def post_with_file(client, token: str, query: str, variables: dict, file_variable: str, filename: str, content: bytes, content_type: str):
    """
    A GraphQL multipart request, with one file at the variable path file_variable (e.g. "reference.file"), sent as
    filename with the content type the client claims
    """
    operations = {"query": query, "variables": variables}
    map_data = {"0": [f"variables.{file_variable}"]}
    data = {"operations": json.dumps(operations), "map": json.dumps(map_data)}
    files = {"0": (filename, content, content_type)}
    headers = with_auth(csrf_token=client.headers["X-CSRF-Token"], auth_token=token)
    return await client.post(GQL_API_PATH, data=data, files=files, headers=headers)


CREATE_LEGAL_FILE = """
    mutation ($reference: LegalFileReferenceInput!, $controlTeamId: ID!, $release: ReadRelease) {
        referencesCreateLegalFile(reference: $reference, controlTeamId: $controlTeamId, release: $release) {
            status result errors { name message }
        }
    }
"""

UPDATE_LEGAL_FILE = """
    mutation ($reference: LegalFileReferenceUpdate!) {
        referencesUpdateLegalFile(reference: $reference) { status result errors { name message } }
    }
"""


async def post_to_create_legal_file_reference(client, token: str, control_team_id: int, filename: str, content: bytes, content_type: str, description: str | None = None):
    return await post_with_file(
        client, token, CREATE_LEGAL_FILE,
        {"reference": {"description": description, "file": None}, "controlTeamId": control_team_id},
        "reference.file", filename, content, content_type
    )


async def post_to_update_legal_file_reference(client, token: str, reference_id: int, filename: str, content: bytes, content_type: str):
    return await post_with_file(
        client, token, UPDATE_LEGAL_FILE,
        {"reference": {"id": reference_id, "file": None}},
        "reference.file", filename, content, content_type
    )
