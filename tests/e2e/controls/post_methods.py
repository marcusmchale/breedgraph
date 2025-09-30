from src.breedgraph.config import GQL_API_PATH
from src.breedgraph.domain.model.controls import ControlledModelLabel, ReadRelease
from tests.e2e.utils import with_auth

from typing import List

async def post_to_set_controls(
        client,
        token: str,
        entity_label: ControlledModelLabel,
        entity_ids: List[int],
        release: ReadRelease
):
    json={
        "query": (
            " mutation ( $entityLabel: ControlledModelLabel!, $entityIds: [Int]!, $release: ReadRelease!) { "
            "  controlsSetControls( "
            "   entityLabel: $entityLabel  "
            "   entityIds: $entityIds "
            "   release: $release "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "entityLabel" : entity_label.name,
            "entityIds" : entity_ids,
            "release" : release.name
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response

async def post_to_controllers(
        client,
        token: str,
        entity_label: ControlledModelLabel,
        entity_ids: List[int]
):
    json={
        "query": (
            " query ( $entityLabel: ControlledModelLabel!, $entityIds: [Int]!) { "
            "  controlsControllers( "
            "   entityLabel: $entityLabel  "
            "   entityIds: $entityIds "
            "  ) { "
            "    status, "
            "    result {"
            "       controls { team {name, id}, release, time }, "
            "       writes { user {id, name } time } "
            "       teams { name, id } "
            "       release "
            "       created "
            "       updated "
            "   }"
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "entityLabel" : entity_label.name,
            "entityIds" : entity_ids
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response