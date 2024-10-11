import pytest_asyncio
from itsdangerous import URLSafeTimedSerializer
import bcrypt

from src.breedgraph.custom_exceptions import IdentityExistsError
from src.breedgraph.domain.commands.accounts import AddAccount, AddEmail
from src.breedgraph.domain.commands.organisations import AddTeam
from src.breedgraph.domain.model.accounts import AccountStored
from src.breedgraph.domain.model.organisations import Organisation, Affiliation, Authorisation, Access
from src.breedgraph.domain.model.ontology import (
    Ontology,
    Subject,
    Trait,
    ObservationMethod, ObservationMethodType,
    Scale, ScaleType,
    Variable,
    LocationType,
    LayoutType
)
from src.breedgraph.domain.model.controls import ReadRelease
from src.breedgraph.domain.model.regions import Region, LocationInput
from src.breedgraph.domain.model.arrangements import Arrangement, LayoutInput

from src.breedgraph.config import LOGIN_SALT, SECRET_KEY
from tests.conftest import user_input_generator


async def create_account(bus, user_input_generator, inviting_user=None):
    user_input = user_input_generator.new_user_input()

    if inviting_user:
        add_email = AddEmail(user=inviting_user, email=user_input.get('email'))
        await bus.handle(add_email)

    password_hash = bcrypt.hashpw(user_input.get('password').encode(), bcrypt.gensalt()).decode()
    cmd = AddAccount(
        name=user_input.get('name'),
        fullname=user_input.get('fullname'),
        password_hash=password_hash,
        email=user_input.get('email')
    )
    await bus.handle(cmd)

async def get_account(bus, user_input_generator, user_id: int):
    async with bus.uow.get_repositories() as uow:
        account = None
        while account is None:
            account = await uow.accounts.get(user_id=user_id)
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
async def first_account(bus, user_input_generator) -> AccountStored:
    return await get_account(bus, user_input_generator, user_id=1)

@pytest_asyncio.fixture(scope="session")
async def second_account(bus, user_input_generator, first_account) -> AccountStored:
    return await get_account(bus, user_input_generator, user_id=2)

@pytest_asyncio.fixture(scope="session")
async def first_user_login_token(first_account) -> str:
    return URLSafeTimedSerializer(SECRET_KEY).dumps(1,salt=LOGIN_SALT)

@pytest_asyncio.fixture(scope="session")
async def second_user_login_token(second_account) -> str:
    return URLSafeTimedSerializer(SECRET_KEY).dumps(2, salt=LOGIN_SALT)

async def create_organisation(bus, user_input_generator, user_id: int):
    team_name = user_input_generator.new_user_input().get('team_name')
    cmd = AddTeam(name=team_name, user=user_id, parent=None)
    await bus.handle(cmd)

async def get_organisation(bus, user_input_generator, user_id: int):
    async with bus.uow.get_repositories(user_id=user_id) as uow:
        organisation = await uow.organisations.get()
        if organisation is None:
            await create_organisation(bus, user_input_generator, user_id=user_id)
            organisation = await uow.organisations.get()
        return organisation

@pytest_asyncio.fixture(scope="session")
async def stored_organisation(bus, user_input_generator, first_account) -> Organisation:
    return await get_organisation(bus, user_input_generator, user_id=first_account.user.id)

@pytest_asyncio.fixture(scope="session")
async def first_account_with_all_affiliations(bus, first_account, stored_organisation):
    async with bus.uow.get_repositories(redacted=False) as uow:
        organisation = await uow.organisations.get(team_id=stored_organisation.get_root_id())
        team = organisation.get_team(stored_organisation.get_root_id())
        for a in Access:
            team.affiliations[Access[a]][first_account.user.id] = Affiliation(
                authorisation=Authorisation.AUTHORISED,
                heritable=False if a == Access.WRITE else True
            )
        await uow.commit()
    return first_account

@pytest_asyncio.fixture(scope="session")
async def basic_ontology(bus, lorem_text_generator) -> Ontology:
    async with bus.uow.get_repositories() as uow:
        ontology: Ontology = await uow.ontologies.get()
        field_subject_id = ontology.add_entry(Subject(name="Field"))
        tree_subject_id = ontology.add_entry(Subject(name="Tree"), parents=[field_subject_id])
        leaf_subject_id = ontology.add_entry(Subject(name="Leaf"), parents=[tree_subject_id])
        rhizosphere_subject_id = ontology.add_entry(Subject(name="Rhizosphere"), parents=[tree_subject_id])
        trait_id = ontology.add_entry(Trait(name="Tree Height"), subjects=[tree_subject_id])
        method_id = ontology.add_entry(
            ObservationMethod(
                name="Tape measure",
                observation_type=ObservationMethodType.MEASUREMENT
            )
        )
        scale_id = ontology.add_entry(
            Scale(name="Millimeters", abbreviation="mm", scale_type=ScaleType.NUMERICAL)
        )
        variable_id = ontology.add_entry(
            Variable(
                name="Tree Height (mm)"
            ),
            trait=trait_id,
            method=method_id,
            scale=scale_id
        )
        # In case country type is already found:
        country_type_id, country_type = ontology.get_entry("Country", label="LocationType")
        if country_type is None:
            country_type_id = ontology.add_entry(LocationType(name="Country", description="Country with ISO-3166 country code"))
        else:
            country_type_id = country_type.id
        state_type_id = ontology.add_entry(
            LocationType(name="State", synonyms=["Department"]),
            parents=[country_type_id]
        )
        ontology.add_entry(
            LocationType(name="Field", synonyms=["Plot"]),
            parents=[state_type_id]
        )
        research_centre_id = ontology.add_entry(
            LocationType(name="Research Centre", synonyms=["Research Station"]),
            parents=[country_type_id, state_type_id]
        )
        ontology.add_entry(
            LocationType(name="Laboratory", synonyms=["Lab"]),
            parents=[research_centre_id]
        )
        adjacency_id = ontology.add_entry(
            LayoutType(
                name="Adjacency",
                synonyms=["Relative Position"],
                description="Positions are given relative to each other in descriptive terms, e.g. 'Top-Right'"
            )
        )
        ontology.add_entry(
            LayoutType(
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
                axes=3
            ),
            parents = [adjacency_id]
        )
        matrix_id = ontology.add_entry(
            LayoutType(
                name="Matrix",
                synonyms=["Array"],
                description="Positions are given by coordinates along each axis"
            )
        )
        ontology.add_entry(
            LayoutType(
                name="Grid",
                synonyms=["2-dimensional Array", "square matrix"],
                description="Positions are given by coordinates along each of two axes",
                axes=2
            ),
            parents = [matrix_id]
        )
        numbered_id = ontology.add_entry(
            LayoutType(
                name="Numbered",
                synonyms=["Indexed"],
                description="Positions are given only by an integer",
                axes=1
            )
        )
        rows_id = ontology.add_entry(
            LayoutType(
                name="Rows",
                synonyms=["Drills"],
                description="Positions are given only by row number",
                axes=1
            ),
            parents=[numbered_id]
        )
        ontology.add_entry(
            LayoutType(
                name="Indexed rows",
                description="First axis is row, second is indexed position within row",
                axes=2
            ),
            parents=[rows_id]
        )
        ontology.add_entry(
            LayoutType(
                name="Measured rows",
                description="First axis is row, second is measured distance from start of row in metres",
                axes=2
            ),
            parents=[rows_id]
        )
        await uow.commit()
        return ontology


@pytest_asyncio.fixture(scope="session")
async def basic_region(
        bus,
        first_account_with_all_affiliations,
        basic_ontology,
        lorem_text_generator
) -> Region:
    async with bus.uow.get_repositories(user_id=first_account_with_all_affiliations.user.id, release=ReadRelease.PUBLIC) as uow:
        # create a new region, from the available countries, it may exist in which case skip to the next
        async for country in bus.read_model.get_countries():
            try:
                region = await uow.regions.create(country)
                break
            except IdentityExistsError:
                pass

        state_type_id, state_type = basic_ontology.get_entry(entry="State", label="LocationType")
        state_id = region.add_location(
            LocationInput(name=lorem_text_generator.new_text(10), type=state_type_id),
            parent_id=region.get_root_id()
        )
        field_type_id, field_type = basic_ontology.get_entry(entry="Field", label="LocationType")
        region.add_location(
            LocationInput(name=lorem_text_generator.new_text(10), type=field_type_id),
            parent_id=state_id
        )
        lab_type_id, lab_type = basic_ontology.get_entry(entry="Lab", label="LocationType")
        region.add_location(
            LocationInput(name=lorem_text_generator.new_text(), type=lab_type_id),
            parent_id=state_id
        )
        await uow.commit()
        return region

@pytest_asyncio.fixture(scope="session")
async def field_arrangement(
        bus,
        first_account_with_all_affiliations,
        basic_ontology,
        basic_region,
        lorem_text_generator
) -> Arrangement:
    field_type_id, field_type = basic_ontology.get_entry("Field", "LocationType")
    field = next(basic_region.yield_locations_by_type(field_type_id))

    row_type_id, row_type = basic_ontology.get_entry("Indexed Rows", "LayoutType")

    layout = LayoutInput(
        location=field.id,
        type=row_type_id,
        axes=["Row", "Index"],
        name="Big Field Planted 2023"
    )

    async with bus.uow.get_repositories(
            user_id=first_account_with_all_affiliations.user.id,
            release=ReadRelease.PUBLIC
    ) as uow:
        arrangement = await uow.arrangements.create(layout)
        await uow.commit()
        return arrangement
