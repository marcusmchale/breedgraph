import httpx
import pytest

from asgi_lifespan import LifespanManager
from fastapi.testclient import TestClient


from asgi_lifespan import LifespanManager
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from typing import AsyncIterator
from src.breedgraph.config import GQL_API_PATH

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


#
#async def post_to_add_email(email: str):
#    json={
#        "query": (
#            " mutation ( "
#            "  $email: String!"
#            " ) { "
#            "  add_email( "
#            "    email: $email, "
#            "  ) { "
#            "    status, "
#            "    result, "
#            "    errors { name, message } "
#            "  } "
#            " } "
#        ),
#        "variables": {
#            "email": f"{email}",
#        }
#    }
#    async with LifespanManager(app):
#        transport = httpx.ASGITransport(app=app)
#        async with httpx.AsyncClient(transport=transport) as client:
#            return await client.post(get_gql_url(), json=json)
#
##async def post_to_add_account(name: str, email: str):
##    json={
#        "query": (
#            " mutation ( "
#            "  $name: String!,"
#            "  $fullname: String,"
#            "  $email: String!,"
#            "  $password: String!"
#            " ) { "
#            "  add_account( "
#            "    name: $name, "
#            "    fullname: $fullname, "
#            "    email: $email, "
#            "    password: $password "
#            "  ) { "
#            "    status, "
#            "    result, "
#            "    errors { name, message } "
#            "  } "
#            " } "
#        ),
#        "variables": {
#            "name": f"{name}",
#            "fullname": f"{name}",
#            "email": f"{email}",
#            "password": "password"
#        }
#    }
#    async with LifespanManager(app):
#        transport = httpx.ASGITransport(app=app)
#        async with httpx.AsyncClient(transport=transport) as client:
#            return await client.post(get_gql_url(), json=json)
#