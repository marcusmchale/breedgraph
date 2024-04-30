import httpx
import pytest

from asgi_lifespan import LifespanManager
from fastapi.testclient import TestClient


from asgi_lifespan import LifespanManager
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from typing import AsyncIterator
from src.breedgraph.config import GQL_API_PATH

from src.breedgraph.domain.model.accounts import Access, Authorisation

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
            "       id, "
            "       parent {name, id,  children {name, id}}, "
            "       children {name, id, parent {name, id}} "
            "       requests "
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


async def post_to_request_read(client, token:str, team: int):
    json = {
        "query": (
            " mutation ( "
            "  $team: Int!"
            " ) { "
            "  request_read( "
            "    team: $team"
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

async def post_to_accounts(client, token:str, user_id: None|int = None):
    json = {
        "query": (
            " query ( "
            "   $user_id : Int "
            " ) { "
            "  accounts ( "
            "  user_id: $user_id"
            "  ) { "
            "    status, "
            "    result {"
            "       user {id, fullname, email},"
            "       affiliations {access, authorisation, team {id, name}} "
            #"       affiliations {access, authorisation } "
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


#
#async def post_to_get_affiliations(client, token:str, access: Access, authorisation: Authorisation):
#    json = {
#        "query": (
#            " query ($access: Access!, $authorisation: Authorisation!) { "
#            "  get_affiliations (access: $access, authorisation: $authorisation) { "
#            "    status, "
#            "    result { "
#            "       user {id, name, fullname, email},"
#            "       team {id, name, fullname, parent_id, child_ids},"
#            "       access,"
#            "       authorisation, heritable"
#            "    }, "
#            "    errors { name, message } "
#            "  } "
#            " } "
#        ),
#        "variables": {
#            "access": access,
#            "authorisation": authorisation
#        }
#    }
#    return await client.post(f"{GQL_API_PATH}/", json=json, headers={"token":token})
#

async def post_to_add_read(client, token:str, user:int, team: int):
    json = {
        "query": (
            " mutation ( "
            "  $user: Int!, "
            "  $team: Int!"
            " ) { "
            "  add_read( "
            "    user: $user, "
            "    team: $team"
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "user": user,
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
            "       user {id, fullname}, "
            "       affiliations {access, authorisation, team {id, name}}"
            "    } , "
            "    errors { name, message } "
            "  } "
            " } "
        )
    }
    return await client.post(f"{GQL_API_PATH}/", json=json, headers={"token":token})