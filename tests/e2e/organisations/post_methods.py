from src.breedgraph.config import GQL_API_PATH
from tests.e2e.utils import with_auth

async def post_to_add_team(client, token:str, name: str, parent: int|None = None):
    if parent:
        json={
            "query": (
                " mutation ( "
                "  $name: String!,"
                "  $fullname: String,"
                "  $parent: Int,"
                " ) { "
                "  add_team( "
                "    name: $name, "
                "    fullname: $fullname, "
                "    parent: $parent "
                "  ) { "
                "    status, "
                "    result, "
                "    errors { name, message } "
                "  } "
                " } "
            ),
            "variables": {
                "name": name,
                "fullname": name,
                "parent": parent
            }
        }
    else:
        json = {
            "query": (
                " mutation ( "
                "  $name: String!,"
                "  $fullname: String"
                " ) { "
                "  add_team( "
                "    name: $name, "
                "    fullname: $fullname"
                "  ) { "
                "    status, "
                "    result, "
                "    errors { name, message } "
                "  } "
                " } "
            ),
            "variables": {
                "name": name,
                "fullname": name
            }
        }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response

async def post_to_organisations(client, token:str):
    json = {
        "query": (
            " query { "
            "  organisations {"
            "    status, "
            "    result { "
            "       name, "
            "       fullname, "
            "       id, "
            "       parent { "
            "           name,"
            "           fullname, "
            "           id, "
            "           children {name, fullname, id}"
            "       }, "
            "       children { "
            "           name, "
            "           fullname, "
            "           id, "
            "           parent {name, fullname, id}, "
            "           children {name, fullname, id}"
            "           affiliations { "
            "               read { user { id, name, fullname, email }, heritable, authorisation } "
            "               write { user { id, name, fullname, email }, heritable, authorisation } "
            "               admin { user { id, name, fullname, email }, heritable, authorisation } "
            "               curate { user { id, name, fullname, email }, heritable, authorisation } "
            "           }, "
            "       }, "
            "       affiliations { "
            "           read { user { id, name, fullname, email }, heritable, authorisation } "
            "           write { user { id, name, fullname, email }, heritable, authorisation } "
            "           admin { user { id, name, fullname, email }, heritable, authorisation } "
            "           curate { user { id, name, fullname, email }, heritable, authorisation } "
            "       }, "
            "    }, "
            "    errors { name, message } "
            "   } "
            " } "
        )
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response


async def post_to_team(client, token:str, team_id: int):
    json = {
        "query": (
            " query ("
            "   $team_id : Int!"
            " ) { "
            "  team ( "
            "  team_id: $team_id,"
            "  ) {"
            "    status, "
            "    result { "
            "       name, "
            "       fullname, "
            "       id, "
            "       parent { "
            "           name,"
            "           fullname, "
            "           id, "
            "           children {name, fullname, id}"
            "       }, "
            "       children { "
            "           name, "
            "           fullname, "
            "           id, "
            "           parent {name, fullname, id}"
            "       }, "
            "       affiliations { "
            "           read { user { id, name, fullname, email }} "
            "           write { user { id, name, fullname, email }} "
            "           admin { user { id, name, fullname, email }} "
            "           curate { user { id, name, fullname, email }} "
            "       }, "
            "    }, "
            "    errors { name, message } "
            "   } "
            " } "
        ),
        "variables": {
            "team_id": team_id,
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response


async def post_to_remove_team(client, token:str, team: int):
    json = {
        "query": (
            " mutation ( "
            "  $team: Int!"
            " ) { "
            "  remove_team( "
            "    team: $team "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "team": team
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response

async def post_to_edit_team(client, token:str, team: int, name: str, fullname: str):
    json = {
        "query": (
            " mutation ( "
            "  $team: Int!,"
            "  $name: String, "
            "  $fullname: String "
            "   "
            " ) { "
            "  edit_team( "
            "    team: $team, "
            "    name: $name, "
            "    fullname: $fullname, "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "team": team,
            "name": name,
            "fullname": fullname
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response
