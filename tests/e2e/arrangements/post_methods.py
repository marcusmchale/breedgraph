from src.breedgraph.config import GQL_API_PATH
from tests.e2e.utils import with_auth

async def post_to_add_layout(
    client,
    token:str,
    layout: dict
):
    json = {
        "query": (
            " mutation ( "
            "  $layout: LayoutInput!"
            " ) { "
            "  add_layout( "
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
            "   $location_id: Int "
            " ) { "
            "  arrangements ( "
            "   location_id: $location_id "
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
            "       release "
            "    }, "
            "    errors { name, message } "
            "   } "
            " } "
        ),
        "variables": {
            "location_id": location_id
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response


async def post_to_layout(client, layout_id: int, token:str = None):
    json = {
        "query": (
            " query ("
            "   $layout_id : Int!"
            " ) { "
            "  layout ( "
            "  layout_id: $layout_id,"
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
            "       release "
            "    }, "
            "    errors { name, message } "
            "   } "
            " } "
        ),
        "variables": {
            "layout_id": layout_id,
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response