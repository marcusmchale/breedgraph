from breedgraph.config import GQL_API_PATH
from breedgraph.domain.model import Access
from tests.breedgraph.e2e.utils import with_auth

async def post_to_create_account(
        client, name: str, email: str, password: str,
        invitation_token: str | None = None, accept_team_ids: list | None = None
):
    json={
        "query": (
            " mutation ( "
            "  $name: String!,"
            "  $fullname: String,"
            "  $email: String!,"
            "  $password: String!,"
            "  $invitationToken: String,"
            "  $acceptTeamIds: [ID!]"
            " ) { "
            "  accountsCreateAccount( "
            "    name: $name, "
            "    fullname: $fullname, "
            "    email: $email, "
            "    password: $password, "
            "    invitationToken: $invitationToken, "
            "    acceptTeamIds: $acceptTeamIds "
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
            "password": password,
            "invitationToken": invitation_token,
            "acceptTeamIds": accept_team_ids
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

async def _post(client, token: str | None, query: str, variables: dict | None = None):
    headers = with_auth(csrf_token=client.headers["X-CSRF-Token"], auth_token=token)
    return await client.post(GQL_API_PATH, json={"query": query, "variables": variables or {}}, headers=headers)

async def post_to_invite(client, token: str, email: str, teams: list | None = None, person_id: int | None = None):
    return await _post(
        client, token,
        " mutation ( $email: String!, $teams: [TeamInvitationInput!], $personId: ID ) { "
        "  accountsInvite( email: $email, teams: $teams, personId: $personId ) { status, result, errors { name, message } } "
        " } ",
        {"email": email, "teams": teams, "personId": person_id}
    )

async def post_to_cancel_invitation(client, token: str, invitation_id: int):
    return await _post(
        client, token,
        " mutation ( $id: ID! ) { accountsCancelInvitation( id: $id ) { status, result, errors { name, message } } } ",
        {"id": invitation_id}
    )

async def post_to_resend_invitation(client, token: str, invitation_id: int):
    return await _post(
        client, token,
        " mutation ( $id: ID! ) { accountsResendInvitation( id: $id ) { status, result, errors { name, message } } } ",
        {"id": invitation_id}
    )

async def post_to_invitation_preview(client, invitation_token: str):
    return await _post(
        client, None,
        " query ( $token: String! ) { accountsInvitation( token: $token ) { "
        "  status, result { email, invitedBy, offersPerson, expiresAt, teams { teamId, teamName, access } }, "
        "  errors { name, message } "
        " } } ",
        {"token": invitation_token}
    )

async def post_to_account_invitations(client, token: str):
    return await _post(
        client, token,
        " query { accountsAccount { status, result { invitations { "
        "  id, email, createdAt, expiresAt, teams { team { id }, access }, person { id } "
        " } }, errors { name, message } } } "
    )


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


async def post_to_request_affiliation(client, token:str, team_id: int, access: Access):
    json = {
        "query": (
            " mutation ( "
            "  $teamId: ID!"
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
            "  $userId: ID!, "
            "  $teamId: ID!"
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
            "  $userId: ID!, "
            "  $teamId: ID!, "
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
