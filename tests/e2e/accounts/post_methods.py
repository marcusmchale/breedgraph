from src.breedgraph.config import GQL_API_PATH
from src.breedgraph.domain.model.controls import Access
from tests.e2e.utils import with_auth

async def post_to_create_account(client, name: str, email: str, password: str):
    json={
        "query": (
            " mutation ( "
            "  $name: String!,"
            "  $fullname: String,"
            "  $email: String!,"
            "  $password: String!"
            " ) { "
            "  accountsCreateAccount( "
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
    return await client.post(GQL_API_PATH, json=json)

async def post_to_login(client, username: str, password: str):
    json={
        "query": (
            " mutation ( "
            "  $username: String!,"
            "  $password: String!,"
            " ) { "
            "  accountsLogin( "
            "    username: $username, "
            "    password: $password"
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "username": username,
            "password": password
        }
    }
    return await client.post(GQL_API_PATH, json=json)


async def post_to_verify_email(client, token: str):
    json={
        "query": (
            " mutation ( "
            "  $token: String!"
            " ) { "
            "  accountsVerifyEmail( "
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
    return await client.post(GQL_API_PATH, json=json)

async def post_to_add_email(client, token: str, email: str):
    json={
        "query": (
            " mutation ( "
            "  $email: String!"
            " ) { "
            "  accountsAddEmail( "
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
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response

async def post_to_remove_email(client, token: str, email: str):
    json={
        "query": (
            " mutation ( "
            "  $email: String!"
            " ) { "
            "  accountsRemoveEmail( "
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
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response


async def post_to_account(client, token:str):
    json = {
        "query": (
            " query { "
            "  accountsAccount { "
            "    status, "
            "    result {"
            "       user {id, name, fullname, email} "
            "    } , "
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


async def post_to_users(client, token:str, user_id: None|int = None):
    json = {
        "query": (
            " query ( "
            "   $userId : Int "
            " ) { "
            "  accountsUsers ( "
            "  userId: $userId"
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
            "userId": user_id,
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response


async def post_to_request_affiliation(client, token:str, team_id: int, access: Access):
    json = {
        "query": (
            " mutation ( "
            "  $teamId: Int!"
            "  $access: Access!"
            " ) { "
            "  accountsRequestAffiliation( "
            "    teamId: $teamId,"
            "    access: $access "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "teamId": team_id,
            "access": access
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response

async def post_to_approve_affiliation(client, token:str, user_id:int, team_id: int, access: Access):
    json = {
        "query": (
            " mutation ( "
            "  $userId: Int!, "
            "  $teamId: Int!"
            "  $access: Access!"
            " ) { "
            "  accountsApproveAffiliation( "
            "    userId: $userId, "
            "    teamId: $teamId, "
            "    access: $access"
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "userId": user_id,
            "teamId": team_id,
            "access": access
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response

async def post_to_remove_affiliation(client, token:str, user_id:int, team_id: int, access: Access):
    json = {
        "query": (
            " mutation ( "
            "  $userId: Int!, "
            "  $teamId: Int!, "
            "  $access: Access!"
            " ) { "
            "  accountsRemoveAffiliation( "
            "    userId: $userId, "
            "    teamId: $teamId,"
            "    access: $access"
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "userId": user_id,
            "teamId": team_id,
            "access": access
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response


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
            "  accountsEditUser( "
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
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response
