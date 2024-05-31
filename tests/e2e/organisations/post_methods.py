from src.breedgraph.config import GQL_API_PATH

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
    return await client.post(f"{GQL_API_PATH}/", json=json, headers={"token":token})


async def post_to_teams(client, token:str, team_id: None|int = None):
    json = {
        "query": (
            " query ("
            "   $team_id : Int"
            " ) { "
            "  teams ( "
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
            "       readers {name, fullname, id, email}, "
            "       writers {name, fullname, id, email}, "
            "       admins {name, fullname, id, email}, "
            "       read_requests {name, fullname, id, email}, "
            "       write_requests {name, fullname, id, email}, "
            "       admin_requests {name, fullname, id, email} "  
            "    }, "
            "    errors { name, message } "
            "   } "
            " } "
        ),
        "variables": {
            "team_id": team_id,
        }
    }
    return await client.post(f"{GQL_API_PATH}/", json=json, headers={"token":token})


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
    return await client.post(f"{GQL_API_PATH}/", json=json, headers={"token":token})

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
    return await client.post(f"{GQL_API_PATH}/", json=json, headers={"token":token})