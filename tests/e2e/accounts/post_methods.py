from src.breedgraph.config import GQL_API_PATH

from src.breedgraph.domain.model.controls import Access

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
            "name": name,
            "fullname": name,
            "email": email,
            "password": password
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
            "username": username,
            "password": password
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
            "token": token
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
            "email": email,
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
            "email": email,
        }
    }
    return await client.post(f"{GQL_API_PATH}/", json=json, headers= {"token": token})


async def post_to_account(client, token:str):
    json = {
        "query": (
            " query { "
            "  account { "
            "    status, "
            "    result {"
            "       user {id, name, fullname, email} "
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


async def post_to_edit_user(
        client,
        token:str,
        name: str|None = None,
        fullname: str|None = None,
        email: str|None = None,
        password: str|None = None
):
    json={
        "query": (
            " mutation ( "
            "  $name: String,"
            "  $fullname: String,"
            "  $email: String,"
            "  $password: String"
            " ) { "
            "  edit_user( "
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
            "name": name,
            "fullname": fullname,
            "email": email,
            "password": password
        }
    }
    return await client.post(f"{GQL_API_PATH}/", json=json, headers={"token":token})
