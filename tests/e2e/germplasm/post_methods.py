from src.breedgraph.config import GQL_API_PATH

from typing import List
from tests.e2e.utils import with_auth

async def post_to_create_germplasm_entry(
        client,
        token: str,
        germplasm_input: dict
):
    json={
        "query": (
            " mutation ( $entry: GermplasmInput! ) { "
            "  germplasmCreateEntry( "
            "   entry: $entry  "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "entry" : germplasm_input
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response

async def post_to_get_germplasm_entries(
        client,
        token: str,
        names: List[str] | None = None,
        entry_ids: List[int] | None = None,
):
    json={
        "query": (
            " query ( "
            "  $names: [String!]"
            "  $entryIds: [Int!]"
            " ) { "
            "  germplasmEntries( "
            "    names: $names "
            "    entryIds: $entryIds "
            "  ) { "
            "    status, "
            "    result { "
            "       id, "
            "       name,"
            "       sources { sourceType, description, source { id, name } }, "
            "       sinks { sourceType, description, sink { id, name } } "
            "   }, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "names": names,
            "entryIds": entry_ids
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response

async def post_to_get_germplasm_crops(
        client,
        token: str
):
    json={
        "query": (
            " query { "
            "  germplasmCrops { "
            "    status, "
            "    result { "
            "       id, "
            "       name,"
            "       sinks { sourceType, description, sink { id, name } } "
            "   }, "
            "    errors { name, message } "
            "  } "
            " } "
        )
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response


async def post_to_update_germplasm_entry(
        client,
        token: str,
        germplasm_input: dict
):
    json={
        "query": (
            " mutation ( $entry: GermplasmUpdate! ) { "
            "  germplasmUpdateEntry( "
            "   entry: $entry  "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "entry" : germplasm_input
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response