import pytest_asyncio
import bcrypt
import asyncio

from numpy import datetime64
from asgi_lifespan import LifespanManager
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from itsdangerous import URLSafeTimedSerializer
from typing import AsyncIterator, AsyncGenerator

import src.breedgraph.adapters.neo4j.unit_of_work
import tests.integration.conftest
from src.breedgraph.service_layer.application import OntologyApplicationService
from tests.utilities.inputs import UserInputGenerator, LoremTextGenerator

from src.breedgraph.main import app
from src.breedgraph.service_layer.infrastructure import unit_of_work
from src.breedgraph.adapters.aiosmtp import EmailNotifications
from src.breedgraph.config import get_base_url, MAIL_HOST, MAIL_PORT, MAIL_USERNAME, MAIL_PASSWORD
from src.breedgraph import bootstrap
from src.breedgraph.service_layer.messagebus import MessageBus
from src.breedgraph.adapters.redis.read_model import ReadModel
from src.breedgraph.custom_exceptions import IdentityExistsError

from src.breedgraph.config import SECRET_KEY, CSRF_SALT, CSRF_EXPIRES

from src.breedgraph.domain.commands.accounts import CreateAccount, AddEmail
from src.breedgraph.domain.commands.organisations import CreateTeam
from src.breedgraph.domain.model.accounts import AccountStored
from src.breedgraph.domain.model.organisations import Organisation, Affiliation, Authorisation, Access
from src.breedgraph.domain.model.ontology import *
from src.breedgraph.domain.model.controls import ReadRelease
from src.breedgraph.domain.model.regions import Region, LocationInput
from src.breedgraph.domain.model.arrangements import Arrangement, LayoutInput
from src.breedgraph.domain.model.blocks import Block, UnitInput, Position

import logging
logger = logging.getLogger(__name__)

@pytest_asyncio.fixture(scope="session")
async def csrf_token() -> str:
    ts = URLSafeTimedSerializer(SECRET_KEY)
    return ts.dumps(
        "test_csrf_token",
        salt=CSRF_SALT
    )

@pytest_asyncio.fixture(scope="session")
def csrf_headers(csrf_token) -> dict:
    return {
        "X-CSRF-Token": csrf_token,
        "Cookie": f"csrf_token={csrf_token}"
    }


@pytest_asyncio.fixture(scope="session")
async def test_app() -> AsyncGenerator[FastAPI, None]:
    async with LifespanManager(app) as manager:
        yield manager.app


@pytest_asyncio.fixture(scope="session")
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
async def neo4j_uow() -> AsyncGenerator[src.breedgraph.adapters.neo4j.unit_of_work.Neo4jUnitOfWork, None]:
    yield src.breedgraph.adapters.neo4j.unit_of_work.Neo4jUnitOfWork()

@pytest_asyncio.fixture(scope="session")
async def uncommitted_neo4j_tx(neo4j_uow, session_database):
    # we require session database just to ensure the cleanup for neo4j tx happens first
    # otherwise the cleanup can't run because of locks on all the created nodes.
    async with neo4j_uow.get_uow() as uow:
        try:
            yield uow.tx
        finally:
            # Ensure explicit rollback and proper cleanup
            try:
                logger.debug("Checking if tx is closed")
                if uow.tx.closed is False:  # Check if transaction is still open
                    logger.debug("tx is not closed, explicit rollback")
                    await uow.rollback()
            except Exception as e:
                logger.debug(f"Error during transaction rollback: {e}")



@pytest_asyncio.fixture(scope="session")
async def email_notifications() -> AsyncGenerator[EmailNotifications, None]:
    yield EmailNotifications()

@pytest_asyncio.fixture(scope="session")
async def bus(neo4j_uow, email_notifications) -> AsyncGenerator[MessageBus, None]:
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
async def read_model(bus) -> AsyncGenerator[ReadModel, None]:
    yield bus.read_model
    # flush read-model when done with tests
    await bus.read_model.connection.flushdb()
    await bus.read_model.connection.aclose()

@pytest_asyncio.fixture(scope="session")
async def session_database(read_model, neo4j_uow) -> AsyncGenerator[None, None]:
    yield
    logger.debug("Starting database cleanup...")
    try:
        async with asyncio.timeout(60):
            async with neo4j_uow.get_uow() as uow:
                await uow.tx.run("MATCH (n) DETACH DELETE n")
                await uow.commit()
    except asyncio.TimeoutError:
        logger.debug("Database cleanup timed out")
    except Exception as e:
        logger.debug(f"Database cleanup failed: {e}")

@pytest_asyncio.fixture(scope="session")
async def user_input_generator() -> AsyncGenerator[UserInputGenerator, None]:
    yield UserInputGenerator()


@pytest_asyncio.fixture(scope="session")
async def lorem_text_generator() -> AsyncGenerator[LoremTextGenerator, None]:
    yield LoremTextGenerator()

async def create_account(bus, user_input_generator, inviting_user=None):
    user_input = user_input_generator.new_user_input()

    if inviting_user:
        add_email = AddEmail(user=inviting_user, email=user_input.get('email'))
        await bus.handle(add_email)

    password_hash = bcrypt.hashpw(user_input.get('password').encode(), bcrypt.gensalt()).decode()
    cmd = CreateAccount(
        name=user_input.get('name'),
        fullname=user_input.get('fullname'),
        password_hash=password_hash,
        email=user_input.get('email')
    )
    await bus.handle(cmd)

async def get_account(bus, user_input_generator, user_id: int) -> AccountStored:
    async with bus.uow.get_uow() as uow:
        account = None
        while account is None:
            account = await uow.repositories.accounts.get(user_id=user_id)
            if account is None:
                if user_id > 1:
                    inviting_user = 1
                else:
                    inviting_user = None
                await create_account(bus, user_input_generator, inviting_user=inviting_user)

        if not account.user.email_verified:
            account.user.email_verified = True
            await uow.commit()

        return account

@pytest_asyncio.fixture(scope="session")
async def first_account(bus, user_input_generator) -> AsyncGenerator[AccountStored, None]:
    yield await get_account(bus, user_input_generator, user_id=1)

@pytest_asyncio.fixture(scope="session")
async def second_account(bus, user_input_generator, first_account) -> AsyncGenerator[AccountStored, None]:
    yield await get_account(bus, user_input_generator, user_id=2)

async def create_organisation(bus, user_input_generator, user_id: int):
    team_name = user_input_generator.new_user_input().get('team_name')
    cmd = CreateTeam(name=team_name, user=user_id, parent=None)
    await bus.handle(cmd)

async def get_organisation(bus, user_input_generator, user_id: int) -> Organisation:
    async with bus.uow.get_uow(user_id=user_id) as uow:
        organisation = await uow.repositories.organisations.get()
        if organisation is None:
            await create_organisation(bus, user_input_generator, user_id=user_id)
            organisation = await uow.repositories.organisations.get()
        return organisation

@pytest_asyncio.fixture(scope="session")
async def stored_organisation(bus, user_input_generator, first_account) -> AsyncGenerator[Organisation, None]:
    yield await get_organisation(bus, user_input_generator, user_id=first_account.user.id)

@pytest_asyncio.fixture(scope="session")
async def first_account_with_all_affiliations(bus, first_account, stored_organisation):
    async with bus.uow.get_uow(redacted=False, user_id=first_account.user.id) as uow:
        organisation = await uow.repositories.organisations.get(team_id=stored_organisation.root.id)
        team = organisation.get_team(stored_organisation.get_root_id())
        for a in Access:
            team.affiliations.set_by_access(
                a,
                first_account.user.id,
                Affiliation(
                    authorisation=Authorisation.AUTHORISED,
                    heritable=False if a == Access.WRITE else True
                )
            )
        await uow.commit()
    yield first_account

@pytest_asyncio.fixture(scope="session")
async def basic_ontology(bus, first_account_with_all_affiliations, lorem_text_generator) -> None:
    async with bus.uow.get_uow(user_id = first_account_with_all_affiliations.user.id) as uow:
        ontology_service = uow.ontology
        field_subject = (
                await ontology_service.get_entry(name='Field', label='Subject') or
                await ontology_service.create_entry(SubjectInput(name="Field"))
        )
        tree_subject = await ontology_service.create_entry(SubjectInput(name="Tree"), parents=[field_subject.id])
        leaf_subject = await ontology_service.create_entry(SubjectInput(name="Leaf"), parents=[tree_subject.id])
        rhizosphere_subject = await ontology_service.create_entry(SubjectInput(name="Rhizosphere"), parents=[tree_subject.id])
        trait = await ontology_service.create_trait(TraitInput(name="Tree Height"), subjects=[tree_subject.id])
        method = await ontology_service.create_entry(
            ObservationMethodInput(
                name="Tape measure",
                observation_type=ObservationMethodType.MEASUREMENT
            )
        )
        mm_scale = await ontology_service.create_entry(
            ScaleInput(name="Millimeters", abbreviation="mm", scale_type=ScaleType.NUMERICAL)
        )
        variable = await ontology_service.create_variable(
            VariableInput(
                name="Tree Height (mm)"
            ),
            trait_id=trait.id,
            observation_method_id=method.id,
            scale_id=mm_scale.id
        )
        genotype_scale = await ontology_service.create_entry(
            ScaleInput(
                name="Genotype",
                synonyms=["Variety", "Cultivar","Germplasm"],
                scale_type=ScaleType.GERMPLASM,
                description="A genotype reference from Germplasm"
            )
        )
        genotype_condition = await ontology_service.create_entry(
            ConditionInput(
                name="Genotype",
                synonyms=["Variety", "Cultivar","Germplasm"],
                description="Genotype of the subject"
            )
        )
        genotypes_condition = await ontology_service.create_entry(
            ConditionInput(
                name="Genotypes",
                description="Genotypes associated with subject"
            )
        )
        genotype_method = await ontology_service.create_entry(
            ControlMethodInput(
                name="Genotype",
                synonyms=["Germplasm"],
                description="Germplasm obtained from controlled source"
            )
        )
        variety_method = await ontology_service.create_entry(
            ControlMethodInput(
                name="Variety",
                description="Varieties as reported by locals"
            )
        )
        await ontology_service.create_factor(
            FactorInput(
                name="Genotype"
            ),
            condition_id=genotype_condition.id,
            control_method_id=genotype_method.id,
            scale_id=genotype_scale.id
        )
        await ontology_service.create_factor(
            FactorInput(
                name="Genotypes"
            ),
            condition_id=genotypes_condition.id,
            control_method_id=variety_method.id,
            scale_id=genotype_scale.id
        )
        # In case country type is already found:
        country_type = await ontology_service.get_entry(name="Country", label="LocationType")
        if country_type is None:
            country_type = await ontology_service.create_entry(LocationTypeInput(name="Country", description="Country with ISO-3166 country code"))

        state_type = await ontology_service.create_entry(
            LocationTypeInput(name="State", synonyms=["Department"]),
            parents=[country_type.id]
        )
        await ontology_service.create_entry(
            LocationTypeInput(name="Field", synonyms=["Plot"]),
            parents=[state_type.id]
        )
        research_centre = await ontology_service.create_entry(
            LocationTypeInput(name="Research Centre", synonyms=["Research Station"]),
            parents=[country_type.id, state_type.id]
        )
        await ontology_service.create_entry(
            LocationTypeInput(name="Laboratory", synonyms=["Lab"]),
            parents=[research_centre.id]
        )
        await ontology_service.create_entry(
            LayoutTypeInput(
                name="Named",
                description="Positions are given by names",
                axes=[AxisType.NOMINAL]
            )
        )
        adjacency = await ontology_service.create_entry(
            LayoutTypeInput(
                name="Adjacency",
                synonyms=["Relative Position"],
                description="Positions are given relative to each other in descriptive terms, e.g. 'Top-Right'",
                axes=[AxisType.NOMINAL]
            )
        )
        await ontology_service.create_entry(
            LayoutTypeInput(
                name="3D adjacency",
                synonyms=["3D Relative Position"],
                description=(
                    "Positions are given relative to each other in descriptive terms "
                    "along each of three axes; "
                    "Depth (front to back), "
                    "Vertical (top to bottom) and "
                    "Horizontal (left to right). "
                    "e.g. 'Rear, Top, Right'"
                ),
                axes=[AxisType.ORDINAL, AxisType.ORDINAL, AxisType.ORDINAL]
            ),
            parents = [adjacency.id]
        )
        matrix = await ontology_service.create_entry(
            LayoutTypeInput(
                name="Matrix",
                synonyms=["Array"],
                description="Positions are given by coordinates along each axis",
            )
        )
        await ontology_service.create_entry(
            LayoutTypeInput(
                name="Grid",
                synonyms=["2-dimensional Array", "square matrix"],
                description="Positions are given by coordinates along each of two perpendicular axes",
                axes=[AxisType.CARTESIAN, AxisType.CARTESIAN]
            ),
            parents = [matrix.id]
        )
        numbered = await ontology_service.create_entry(
            LayoutTypeInput(
                name="Numbered",
                synonyms=["Indexed"],
                description="Positions are given only by an integer",
                axes=[AxisType.ORDINAL]
            )
        )
        rows = await ontology_service.create_entry(
            LayoutTypeInput(
                name="Rows",
                synonyms=["Drills"],
                description="Positions are given only by row number",
                axes=[AxisType.ORDINAL]
            ),
            parents=[numbered.id]
        )
        await ontology_service.create_entry(
            LayoutTypeInput(
                name="Indexed rows",
                description="First axis is row, second is indexed position within row",
                axes=[AxisType.ORDINAL, AxisType.ORDINAL]
            ),
            parents=[rows.id]
        )
        await ontology_service.create_entry(
            LayoutTypeInput(
                name="Measured rows",
                description="First axis is row, second is measured distance from start of row in metres",
                axes=[AxisType.ORDINAL, AxisType.COORDINATE]
            ),
            parents=[rows.id]
        )
        await uow.commit()

@pytest_asyncio.fixture(scope="session")
async def basic_region(
        bus,
        first_account_with_all_affiliations,
        basic_ontology,
        lorem_text_generator
) -> AsyncGenerator[Region, None]:
    async with bus.uow.get_uow(
            user_id=first_account_with_all_affiliations.user.id,
            release=ReadRelease.PUBLIC,
    ) as uow:
        # create a new region, from the available countries, it may exist in which case skip to the next
        async for country in bus.read_model.get_countries():
            try:
                region = await uow.repositories.regions.create(country)
                break

            except IdentityExistsError:
                pass
        state_type = await uow.ontology.get_entry(name="State", label="LocationType")
        state_id = region.add_location(
            LocationInput(name=lorem_text_generator.new_text(10), type=state_type.id),
            parent_id=region.get_root_id()
        )
        field_type = await uow.ontology.get_entry(name="Field", label="LocationType")
        region.add_location(
            LocationInput(name=lorem_text_generator.new_text(10), type=field_type.id),
            parent_id=state_id
        )
        lab_type = await uow.ontology.get_entry(name="Laboratory", label="LocationType")
        region.add_location(
            LocationInput(name=lorem_text_generator.new_text(), type=lab_type.id),
            parent_id=state_id
        )
        await uow.commit()
        yield region

@pytest_asyncio.fixture(scope="session")
async def field_arrangement(
        bus,
        first_account_with_all_affiliations,
        basic_ontology,
        basic_region,
        lorem_text_generator
) -> AsyncGenerator[Arrangement, None]:
    async with bus.uow.get_uow(
            user_id=first_account_with_all_affiliations.user.id,
            release=ReadRelease.PUBLIC
    ) as uow:
        field_type = await uow.ontology.get_entry(name="Field", label="LocationType")
        field = next(basic_region.yield_locations_by_type(field_type.id))

        row_type = await uow.ontology.get_entry(name="Indexed Rows", label="LayoutType")
        layout = LayoutInput(
            location=field.id,
            type=row_type.id,
            axes=["Row", "Plant"],
            name="Big Field Planted 2023"
        )
        arrangement = await uow.repositories.arrangements.create(layout)
        await uow.commit()
        yield arrangement

@pytest_asyncio.fixture(scope="session")
async def basic_block(
        bus,
        first_account_with_all_affiliations,
        basic_ontology,
        basic_region,
        field_arrangement,
        lorem_text_generator
) -> AsyncGenerator[Block, None]:
    async with bus.uow.get_uow(first_account_with_all_affiliations.user.id) as uow:
        field_location_type = await uow.ontology.get_entry(name="Field", label="LocationType")
        field_location = next(basic_region.yield_locations_by_type(field_location_type.id))

        field_subject = await uow.ontology.get_entry(name="Field", label="Subject")
        tree_subject = await uow.ontology.get_entry(name="Tree", label="Subject")

        field_unit = UnitInput(
            subject=field_subject.id,
            name="First Field",
            synonyms=['Field 1'],
            description="The big field at the end of the road",
            positions=[
                Position(
                    location=field_location.id,
                    start=datetime64("2010")
                )
            ]
        )
        tree_unit = UnitInput(
            subject=tree_subject.id,
            name="First Tree",
            synonyms=['Tree 1'],
            positions=[
                Position(
                    location=field_location.id,
                    start=datetime64("2010"),
                    layout=field_arrangement.get_root_id(),
                    coordinates=["1", "1"],
                    end=datetime64("2025")
                )
            ]
        )

        block = await uow.repositories.blocks.create(field_unit)
        block.add_unit(unit=tree_unit, parents=[block.get_root_id()])
        await uow.commit()
        yield block