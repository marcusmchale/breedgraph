import pytest_asyncio

import asyncio
import redis.asyncio as redis
from asgi_lifespan import LifespanManager
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from itsdangerous import URLSafeTimedSerializer

from src.breedgraph.main import app
from src.breedgraph.domain.model.accounts import UserInput, AccountInput, OntologyRole
from src.breedgraph.domain.model.ontology import *

from src.breedgraph.adapters.redis import RedisLoader
from src.breedgraph.adapters.redis import RedisStateStore
from src.breedgraph.adapters.neo4j import Neo4jUnitOfWorkFactory
from src.breedgraph.adapters.neo4j import Neo4jViewsFactory
from src.breedgraph.adapters.neo4j import queries

from src.breedgraph.service_layer.messagebus import MessageBus

from tests.utilities.inputs import UserInputGenerator, LoremTextGenerator
from tests.scenarios import (
    AccountBuilder,
    OntologyBuilder,
    RegionBuilder,
    ProgramBuilder,
    BlockBuilder,
    PersonBuilder,
    ArrangementBuilder
)

from typing import Dict, cast, AsyncGenerator

from src.breedgraph.config import (
    SECRET_KEY, CSRF_SALT,
    MAIL_USERNAME, MAIL_HOST,
    get_base_url, get_redis_host_and_port
)

import logging
logger = logging.getLogger(__name__)

@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def csrf_token() -> str | bytes:
    ts = URLSafeTimedSerializer(SECRET_KEY)
    return ts.dumps("test_csrf_token", salt=CSRF_SALT)

@pytest_asyncio.fixture(scope="session", loop_scope="session")
def csrf_headers(csrf_token) -> dict:
    return {
        "X-CSRF-Token": csrf_token,
        "Cookie": f"csrf_token={csrf_token}"
    }

@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def login_token_factory(bus):
    def create_token(user_id: int) -> str:
        return bus.auth_service.create_login_token(user_id)

    return create_token


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def test_app() -> AsyncGenerator[FastAPI, None]:
    async with LifespanManager(app) as manager:
        yield app
        #yield manager.app

@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def client(test_app: FastAPI, csrf_headers: dict) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=test_app)
    async with AsyncClient(
        transport=transport,
        base_url=get_base_url(),
        headers=csrf_headers,
        cookies={}
    ) as client:
        yield client

@pytest_asyncio.fixture(scope="session")
async def user_input_generator() -> AsyncGenerator[UserInputGenerator, None]:
    yield UserInputGenerator()

@pytest_asyncio.fixture(scope="session")
async def lorem_text_generator() -> AsyncGenerator[LoremTextGenerator, None]:
    yield LoremTextGenerator()

async def init_neo4j(uow_factory) -> None:
    async with uow_factory.get_uow() as uow:
        result = await uow.tx.run(queries['infrastructure']['is_empty'])
        is_empty = (await result.single(strict=True))["empty"]
        if not is_empty:
            raise Exception("Database is not empty, aborting test...")

        system_account = await uow.repositories.accounts.create(
            AccountInput(
                user=UserInput(
                    name='system',
                    fullname='system user',
                    email=f'{MAIL_USERNAME}@{MAIL_HOST}',
                    password_hash="",
                    ontology_role=OntologyRole('admin')
                )
            )
        )
        await uow.commit()

    async with uow_factory.get_uow(user_id=system_account.user.id) as uow:
        await uow.ontology.commit_version(
            version_change=None,
            comment="Initial version"
        )
        country_type_input = LocationTypeInput(
            name='Country',
            description='Country and three digit code according to ISO 3166-1 alpha-3'
        )
        await uow.ontology.create_entry(entry=country_type_input)
        await uow.commit()

async def init_redis(uow_factory) -> None:

    async def is_redis_empty(con):
        cursor = 0
        while True:
            cursor, keys = await con.scan(cursor=cursor)
            if keys:
                return False  # Found some keys, Redis is not empty
            if cursor == 0:
                break
        return True  # No keys found, Redis is empty

    host, port = get_redis_host_and_port()
    connection = await redis.Redis(host=host, port=port, db=0)
    try:
        assert await is_redis_empty(connection), "Redis is not empty, aborting test!"
        loader = RedisLoader(connection, uow_factory.driver)
        await loader.load_read_model()
    finally:
        await connection.aclose()

async def flush_neo4j(uow_factory: Neo4jUnitOfWorkFactory) -> None:
    try:
        async with asyncio.timeout(60):
            async with uow_factory.get_uow() as uow:
                await uow.tx.run("MATCH (n) DETACH DELETE n")
                await uow.commit()
    except asyncio.TimeoutError:
        logger.debug("Neo4j cleanup timed out")

async def flush_redis(state_store: RedisStateStore) -> None:
    logger.debug("Starting redis cleanup...")
    try:
        await state_store.connection.flushdb()
    except asyncio.TimeoutError:
        logger.debug("Redis cleanup timed out")
    except Exception as e:
        logger.debug(f"Redis cleanup failed: {e}")

@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def bus(test_app: FastAPI) -> MessageBus:
    return test_app.bus

@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def uow_factory(bus) -> Neo4jUnitOfWorkFactory:
    return cast(Neo4jUnitOfWorkFactory, bus.uow_factory)


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def views_factory(bus) -> Neo4jViewsFactory:
    return cast(Neo4jViewsFactory, bus.views_factory)


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def state_store(bus) -> RedisStateStore:
    return cast(RedisStateStore, bus.state_store)


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def event_queue(bus) -> asyncio.Queue:
    return bus.event_queue

@pytest_asyncio.fixture(scope="module", loop_scope="session", autouse=True)
async def isolated_state(
        uow_factory: Neo4jUnitOfWorkFactory,
        state_store: RedisStateStore,
        event_queue: asyncio.Queue
) -> AsyncGenerator[None, None]:
    await event_queue.join()
    logger.debug("Cleaning state before test")
    await flush_neo4j(uow_factory)
    await flush_redis(state_store)
    logger.debug("Setting up new state")
    await init_neo4j(uow_factory)
    await init_redis(uow_factory)

    yield
    try:
        async with asyncio.timeout(5):
            await event_queue.join()
    except TimeoutError:
        logger.error("Timed out waiting for event queue to drain")
        logger.error(f"queue size: {event_queue.qsize()}")

    logger.debug("Cleaning state after test")
    await flush_neo4j(uow_factory)
    await flush_redis(state_store)


async def build_account_with_affiliations(uow_factory: Neo4jUnitOfWorkFactory) -> int:
    account_builder = AccountBuilder(uow_factory=uow_factory)
    account_ids = await account_builder.account_with_affiliations()
    return account_ids['user_id']

async def build_location(uow_factory: Neo4jUnitOfWorkFactory, state_store: RedisStateStore, user_id: int) -> int:
    ontology_location_ids = await OntologyBuilder(uow_factory).location_types(user_id=user_id)
    region_builder = RegionBuilder(uow_factory=uow_factory, state_store=state_store)
    location_ids = await region_builder.region(
        user_id=user_id,
        ontology_location_state=ontology_location_ids['ontology_location_state'],
        ontology_location_field=ontology_location_ids['ontology_location_field'],
        ontology_location_lab=ontology_location_ids['ontology_location_lab']
    )
    return location_ids['location_field_id']


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def user_registration_context(isolated_state, login_token_factory):
    return {
        'login_token_user_1':  login_token_factory(user_id=2),
        'login_token_user_2': login_token_factory(user_id=3)
    }

@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def control_context(isolated_state, uow_factory, state_store) -> Dict[str, int]:
    user_id = await build_account_with_affiliations(uow_factory)
    location_id = await build_location(uow_factory, state_store, user_id)
    return {
        'user_id': user_id,
        'location_id': location_id
    }


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def layout_build_context(isolated_state, uow_factory, state_store) -> Dict[str, int]:
    user_id = await build_account_with_affiliations(uow_factory)
    location_id = await build_location(uow_factory, state_store, user_id)
    layout_types = await OntologyBuilder(uow_factory=uow_factory).layout_types(user_id=user_id)
    return {
        'user_id': user_id,
        'location_id': location_id,
        **layout_types
    }

@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def block_build_context(isolated_state, uow_factory, state_store) -> Dict[str, int]:
    user_id = await build_account_with_affiliations(uow_factory)
    location_types = await OntologyBuilder(uow_factory=uow_factory).location_types(user_id=user_id)
    layout_types = await OntologyBuilder(uow_factory=uow_factory).layout_types(user_id=user_id)
    subject_types = await OntologyBuilder(uow_factory=uow_factory).subject_types(user_id=user_id)

    location_ids = await RegionBuilder(uow_factory, state_store).region(
        user_id=user_id,
        ontology_location_state=location_types['ontology_location_state'],
        ontology_location_field=location_types['ontology_location_field'],
        ontology_location_lab=location_types['ontology_location_lab']
    )
    location_id = location_ids['location_field_id']
    layout_ids = await ArrangementBuilder(uow_factory).arrangement(
        user_id=user_id,
        location_id=location_id,
        ontology_layout_named=layout_types['ontology_layout_named'],
        ontology_layout_3d=layout_types['ontology_layout_3d'],
        ontology_layout_grid=layout_types['ontology_layout_grid']
    )
    layout_id = layout_ids['layout_shelf_id']
    return {
        'user_id': user_id,
        'location_id': location_id,
        'layout_id': layout_id,
        **location_ids,
        **subject_types,
        **location_types
    }

@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def dataset_build_context(isolated_state, uow_factory) -> Dict[str, int]:
    user_id = await build_account_with_affiliations(uow_factory)

    program_builder = ProgramBuilder(uow_factory=uow_factory)
    program_ids = await program_builder.program_trial_study(user_id)
    study_id = program_ids['study_id']

    variable_ids = await OntologyBuilder(uow_factory=uow_factory).variable_tree_height(user_id)
    unit_id = await BlockBuilder(uow_factory=uow_factory).unit(user_id=user_id)
    person_id = await PersonBuilder(uow_factory=uow_factory).person(user_id=user_id)
    return {
        'user_id': user_id,
        'study_id': study_id,
        'concept_id': variable_ids['ontology_variable_height'],
        'unit_id': unit_id,
        'person_id': person_id
    }

@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def organisation_build_context(isolated_state, uow_factory) -> Dict[str, int]:
    user_id = await AccountBuilder(uow_factory=uow_factory).account()
    user_id_2 = await AccountBuilder(uow_factory=uow_factory).account()
    return {
        'user_id': user_id,
        'user_id_1': user_id,
        'user_id_2': user_id_2
    }

@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def person_build_context(isolated_state, uow_factory) -> Dict[str, int]:
    account_builder = AccountBuilder(uow_factory=uow_factory)
    account_ids = await account_builder.account_with_affiliations()
    user_id_2 = await account_builder.account()
    return {
        'user_id': account_ids['user_id'],
        'user_id_1': account_ids['user_id'],
        'user_id_2': user_id_2,
        'team_id': account_ids['team_id']
    }

@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def program_build_context(isolated_state, uow_factory) -> Dict[str, int]:
    user_id = await build_account_with_affiliations(uow_factory)
    return {
        'user_id': user_id
    }

@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def reference_build_context(isolated_state, uow_factory) -> Dict[str, int]:
    user_id = await build_account_with_affiliations(uow_factory)
    return {
        'user_id': user_id
    }

@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def region_build_context(isolated_state, uow_factory) -> Dict[str, int]:
    account_builder = AccountBuilder(uow_factory=uow_factory)
    account_ids = await account_builder.account_with_affiliations()
    user_id = account_ids['user_id']
    team_id = account_ids['team_id']
    user_id_2 = await build_account_with_affiliations(uow_factory)
    location_types = await OntologyBuilder(uow_factory=uow_factory).location_types(user_id=user_id)
    return {
        'user_id': user_id,
        'team_id': team_id,
        'user_id_1': user_id,
        'user_id_2': user_id_2,
        **location_types
    }

@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def germplasm_build_context(isolated_state, uow_factory) -> Dict[str, int]:
    account_builder = AccountBuilder(uow_factory=uow_factory)
    account_ids = await account_builder.account_with_affiliations()
    user_id = account_ids['user_id']
    team_id = account_ids['team_id']
    user_id_2 = await build_account_with_affiliations(uow_factory)
    return {
        'user_id': user_id,
        'team_id': team_id,
        'user_id_1': user_id,
        'user_id_2': user_id_2
    }

@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def ontology_build_context(isolated_state, uow_factory) -> Dict[str, int]:
    account_builder = AccountBuilder(uow_factory=uow_factory)
    account_1_ids = await account_builder.account_with_affiliations(ontology_role=OntologyRole.ADMIN)
    account_2_ids = await account_builder.account_with_affiliations(ontology_role=OntologyRole.CONTRIBUTOR)
    user_id = account_1_ids['user_id']
    variable_components = await OntologyBuilder(
        uow_factory=uow_factory
    ).basic_variable_components(user_id=user_id)

    return {
        'user_id': user_id,
        'user_id_1': user_id,
        'team_id': account_1_ids['team_id'],
        'user_id_2': account_2_ids['user_id'],
        **variable_components
    }
