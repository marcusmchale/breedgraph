from src.breedgraph.config import GQL_API_PATH
from tests.e2e.utils import with_auth
from typing import List

async def post_to_create_layout(
    client,
    token:str,
    layout: dict
):
    json = {
        "query": (
            " mutation ( "
            "  $layout: LayoutInput!"
            " ) { "
            "  arrangementsCreateLayout( "
            "    layout: $layout, "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "layout": layout
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response

async def post_to_arrangements(client, location_id: int=None, token:str = None):
    json = {
        "query": (
            " query ( "
            "   $locationId: Int "
            " ) { "
            "  arrangements ( "
            "   locationId: $locationId "
            " ) { "
            "    status, "
            "    result { "
            "       id, "
            "       name, "
            "       axes, "
            "       type { id, name } "
            "       parent {id, name, axes, type {id, name} } "
            "       position, "
            "       children {id, name, axes, type {id, name} } "
            "    }, "
            "    errors { name, message } "
            "   } "
            " } "
        ),
        "variables": {
            "locationId": location_id
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response


async def post_to_layouts(client, layout_ids: List[int], token:str = None):
    json = {
        "query": (
            " query ("
            "   $layoutIds : [Int!]!"
            " ) { "
            "  arrangementsLayouts ( "
            "  layoutIds: $layoutIds,"
            "  ) {"
            "    status, "
            "    result { "
            "       id, "
            "       name, "
            "       axes "     
            "       type {id, name} "
            "       parent {id, name, axes, type {id, name} } "
            "       position, "
            "       children {id, name, axes, type {id, name} } "
            "    }, "
            "    errors { name, message } "
            "   } "
            " } "
        ),
        "variables": {
            "layoutIds": layout_ids,
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response