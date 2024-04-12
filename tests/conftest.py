import pytest_asyncio

from faker import Faker

from asgi_lifespan import LifespanManager
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from typing import AsyncIterator

from src.breedgraph.main import app
from src.breedgraph.service_layer.unit_of_work import Neo4jUnitOfWork

from src.breedgraph.config import get_base_url, MAIL_DOMAIN, MAIL_USERNAME



@pytest_asyncio.fixture(scope="session")
async def clear_database() -> None:
    async with Neo4jUnitOfWork() as uow:
        await uow.tx.run("MATCH (n) DETACH DELETE n")
        await uow.commit()

@pytest_asyncio.fixture(scope="session")
async def test_app() -> FastAPI:
    async with LifespanManager(app) as manager:
        yield manager.app

@pytest_asyncio.fixture(scope="session")
async def client(test_app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url=get_base_url()) as client:
        yield client


class UserInputGenerator:
    def __init__(self):
        self.fake = Faker()
        self.user_inputs = list()

    def new_user_input(self):
        user_input = {
            "name": self.fake.unique.name(),
            "email": f"{MAIL_USERNAME}+_test_user_{len(self.user_inputs)+1}@{MAIL_DOMAIN}",
            "password": self.fake.password(),
            "team": self.fake.company()
        }
        self.user_inputs.append(user_input)
        return user_input

@pytest_asyncio.fixture(scope="session")
async def user_input_generator() -> UserInputGenerator:
    yield UserInputGenerator()