import asyncio
import pytest
import pytest_asyncio


from asgi_lifespan import LifespanManager
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from typing import AsyncIterator

from src.breedgraph.main import app
from src.breedgraph.service_layer import unit_of_work
from src.breedgraph.adapters.notifications import notifications
from src.breedgraph.config import get_base_url, MAIL_HOST, MAIL_PORT, MAIL_USERNAME, MAIL_PASSWORD
from src.breedgraph import bootstrap
from src.breedgraph.service_layer.messagebus import MessageBus
from src.breedgraph.adapters.redis.read_model import ReadModel

from tests.inputs import UserInputGenerator, LoremTextGenerator

@pytest_asyncio.fixture(scope="session")
async def test_app() -> FastAPI:
    async with LifespanManager(app) as manager:
        yield manager.app

@pytest_asyncio.fixture(scope="session")
async def client(test_app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url=get_base_url()) as client:
        yield client

@pytest_asyncio.fixture(scope="session")
async def neo4j_uow() -> unit_of_work.Neo4jUnitOfWork:
    yield unit_of_work.Neo4jUnitOfWork()

@pytest_asyncio.fixture(scope="session")
async def neo4j_tx(neo4j_uow):
    async with neo4j_uow.get_repositories() as uow:
        yield uow.tx

@pytest_asyncio.fixture(scope="session")
async def email_notifications() -> notifications.EmailNotifications:
    yield notifications.EmailNotifications()

@pytest_asyncio.fixture(scope="session")
async def bus(neo4j_uow, email_notifications) -> MessageBus:
    bus = await bootstrap.bootstrap(
        uow=neo4j_uow,
        notifications=email_notifications
    )
    yield bus
#
#@pytest_asyncio.fixture(scope="session")
#async def quiet_bus() -> MessageBus:
#    bus = await bootstrap.bootstrap(
#        uow=unit_of_work.Neo4jUnitOfWork(),
#        notifications=notifications.FakeNotifications()
#    )
#    yield bus
#

@pytest_asyncio.fixture(scope="session")
async def read_model(bus) -> ReadModel:
    yield bus.read_model
    # flush read-model when done
    await bus.read_model.connection.flushdb()
    await bus.read_model.connection.aclose()

@pytest_asyncio.fixture(scope="session")
async def session_database(read_model) -> None:
    yield
    # flush db when done
    uow = unit_of_work.Neo4jUnitOfWork()
    async with uow.get_repositories() as uow:
        await uow.tx.run("MATCH (n) DETACH DELETE n")
        await uow.commit()

@pytest_asyncio.fixture(scope="session")
async def user_input_generator() -> UserInputGenerator:
    yield UserInputGenerator()


@pytest_asyncio.fixture(scope="session")
async def lorem_text_generator() -> LoremTextGenerator:
    yield LoremTextGenerator()
