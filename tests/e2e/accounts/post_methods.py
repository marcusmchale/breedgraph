from src.breedgraph.config import GQL_API_PATH

from src.breedgraph.domain.model.accounts import Access

async def post_to_add_first_account(client, name: str, email: str, password: str, team_name: str):
    json={
        "query": (
            " mutation ( "
            "  $name: String!,"
            "  $fullname: String,"
            "  $email: String!,"
            "  $password: String!,"
            "  $team_name: String!,"
            "  $team_fullname: String"
            " ) { "
            "  add_first_account( "
            "    name: $name, "
            "    fullname: $fullname, "
            "    email: $email, "
            "    password: $password, "
            "    team_name: $team_name, "
            "    team_fullname: $team_fullname"
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "name": f"{name}",
            "fullname": f"{name}",
            "email": f"{email}",
            "password": f"{password}",
            "team_name": f"{team_name}",
            "team_fullname": f"{team_name}"
        }
    }
    return await client.post(f"{GQL_API_PATH}/", json=json)

async def post_to_login(client, username: str, password: str):
    json={
        "query": (
            " mutation ( "
            "  $username: String!,"
            "  $password: String!,"
            " ) { "
            "  login( "
            "    username: $username, "
            "    password: $password"
            "  ) { "
            "    status, "
            "    result {token_type, access_token}, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "username": f"{username}",
            "password": f"{password}"
        }
    }
    return await client.post(f"{GQL_API_PATH}/", json=json)


async def post_to_verify_email(client, token: str):
    json={
        "query": (
            " mutation ( "
            "  $token: String!"
            " ) { "
            "  verify_email( "
            "    token: $token "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "token": f"{token}"
        }
    }
    return await client.post(f"{GQL_API_PATH}/", json=json)

async def post_to_add_email(client, token: str, email: str):
    json={
        "query": (
            " mutation ( "
            "  $email: String!"
            " ) { "
            "  add_email( "
            "    email: $email, "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "email": f"{email}",
        }
    }
    return await client.post(f"{GQL_API_PATH}/", json=json, headers= {"token": token})

async def post_to_remove_email(client, token: str, email: str):
    json={
        "query": (
            " mutation ( "
            "  $email: String!"
            " ) { "
            "  remove_email( "
            "    email: $email, "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "email": f"{email}",
        }
    }
    return await client.post(f"{GQL_API_PATH}/", json=json, headers= {"token": token})


async def post_to_add_account(client, name: str, email: str, password: str):
    json={
        "query": (
            " mutation ( "
            "  $name: String!,"
            "  $fullname: String,"
            "  $email: String!,"
            "  $password: String!"
            " ) { "
            "  add_account( "
            "    name: $name, "
            "    fullname: $fullname, "
            "    email: $email, "
            "    password: $password "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "name": f"{name}",
            "fullname": f"{name}",
            "email": f"{email}",
            "password": f"{password}"
        }
    }
    return await client.post(f"{GQL_API_PATH}/", json=json)


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
                "name": f"{name}",
                "fullname": f"{name}",
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
                "name": f"{name}",
                "fullname": f"{name}"
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


async def post_to_account(client, token:str):
    json = {
        "query": (
            " query { "
            "  account { "
            "    status, "
            "    result {"
            "       user {id, name, fullname, email}, "
            "       reads {id, name}"
            "       writes {id, name}"
            "       admins {id, name}"
            "    } , "
            "    errors { name, message } "
            "  } "
            " } "
        )
    }
    return await client.post(f"{GQL_API_PATH}/", json=json, headers={"token":token})


async def post_to_users(client, token:str, user_id: None|int = None):
    json = {
        "query": (
            " query ( "
            "   $user_id : Int "
            " ) { "
            "  users ( "
            "  user_id: $user_id"
            "  ) { "
            "    status, "
            "    result {"
            "       id, fullname, email,"
            "   },"
            "    errors { name, message } "
            "   } "
            " } "
        ),
        "variables": {
            "user_id": user_id,
        }
    }
    return await client.post(f"{GQL_API_PATH}/", json=json, headers={"token":token})


async def post_to_request_affiliation(client, token:str, team: int, access: Access):
    json = {
        "query": (
            " mutation ( "
            "  $team: Int!"
            "  $access: Access!"
            " ) { "
            "  request_affiliation( "
            "    team: $team,"
            "    access: $access "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "team": team,
            "access": access
        }
    }
    return await client.post(f"{GQL_API_PATH}/", json=json, headers={"token":token})

async def post_to_approve_affiliation(client, token:str, user:int, team: int, access: Access):
    json = {
        "query": (
            " mutation ( "
            "  $user: Int!, "
            "  $team: Int!"
            "  $access: Access!"
            " ) { "
            "  approve_affiliation( "
            "    user: $user, "
            "    team: $team, "
            "    access: $access"
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "user": user,
            "team": team,
            "access": access
        }
    }
    return await client.post(f"{GQL_API_PATH}/", json=json, headers={"token":token})

async def post_to_remove_affiliation(client, token:str, user:int, team: int, access: Access):
    json = {
        "query": (
            " mutation ( "
            "  $user: Int!, "
            "  $team: Int!, "
            "  $access: Access!"
            " ) { "
            "  remove_affiliation( "
            "    user: $user, "
            "    team: $team,"
            "    access: $access"
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "user": user,
            "team": team,
            "access": access
        }
    }
    return await client.post(f"{GQL_API_PATH}/", json=json, headers={"token":token})