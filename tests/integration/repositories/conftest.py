from typing import AsyncGenerator
import pytest_asyncio

from src.breedgraph.service_layer.controllers_service import TestControllersService

from src.breedgraph.adapters.repositories.accounts import Neo4jAccountRepository
from src.breedgraph.adapters.repositories.arrangements import Neo4jArrangementsRepository
from src.breedgraph.adapters.repositories.blocks import Neo4jBlocksRepository
from src.breedgraph.adapters.repositories.germplasms import Neo4jGermplasmRepository
from src.breedgraph.adapters.repositories.organisations import Neo4jOrganisationsRepository
from src.breedgraph.adapters.repositories.people import Neo4jPeopleRepository
from src.breedgraph.adapters.repositories.programs import Neo4jProgramsRepository
from src.breedgraph.adapters.repositories.references import Neo4jReferencesRepository
from src.breedgraph.adapters.repositories.ontologies import Neo4jOntologyRepository
from src.breedgraph.adapters.repositories.datasets import Neo4jDatasetsRepository

from src.breedgraph.domain.model.controls import ReadRelease
from src.breedgraph.domain.model.accounts import AccountStored
from src.breedgraph.domain.model.germplasm import (
    Germplasm,
    GermplasmEntryInput,
    GermplasmEntryStored,
    GermplasmSourceType,
    Reproduction
)
from src.breedgraph.domain.model.arrangements import Arrangement, LayoutInput
from src.breedgraph.domain.model.organisations import TeamInput, Organisation, Access
from src.breedgraph.domain.model.blocks import UnitInput, UnitStored, Block, Position

from src.breedgraph.domain.model.ontology import (
    Ontology,
    Subject,
    GermplasmMethod,
    LocationType,
    LayoutType,
    Variable, Trait, Scale, ScaleType, ObservationMethod, ObservationMethodType, AxisType
)
from src.breedgraph.domain.model.people import PersonInput
from src.breedgraph.domain.model.references import ExternalReferenceInput, ExternalReferenceStored

from src.breedgraph.views.regions import countries
from src.breedgraph.adapters.repositories.regions import Neo4jRegionsRepository
from src.breedgraph.domain.model.regions import LocationInput, LocationStored, Region

from src.breedgraph.domain.model.datasets import DataSetInput, DataSetStored, DataRecordInput

from tests.integration.repositories.test_accounts_repository import create_account_input

@pytest_asyncio.fixture(scope="session")
async def test_controllers_service(stored_account, stored_organisation) -> AsyncGenerator[TestControllersService, None]:
    """Test controllers service fixture for integration tests"""
    yield TestControllersService()

@pytest_asyncio.fixture(scope="session")
async def accounts_repo(neo4j_tx) -> AsyncGenerator[Neo4jAccountRepository, None]:
    yield Neo4jAccountRepository(neo4j_tx)

@pytest_asyncio.fixture(scope="session")
async def stored_account(accounts_repo, user_input_generator) -> AsyncGenerator[AccountStored, None]:
    account_input = await create_account_input(user_input_generator)
    stored_account: AccountStored = await accounts_repo.create(account_input)
    await accounts_repo.update_seen()
    yield stored_account

@pytest_asyncio.fixture(scope="session")
async def second_account(accounts_repo, user_input_generator) -> AsyncGenerator[AccountStored, None]:
    account_input = await create_account_input(user_input_generator)
    second_account: AccountStored = await accounts_repo.create(account_input)
    await accounts_repo.update_seen()
    yield second_account

@pytest_asyncio.fixture(scope='session')
async def organisations_repo(neo4j_tx, stored_account) -> AsyncGenerator[Neo4jOrganisationsRepository, None]:
    yield Neo4jOrganisationsRepository(neo4j_tx, user_id=stored_account.user.id)

@pytest_asyncio.fixture(scope="session")
async def stored_organisation(user_input_generator, organisations_repo) -> AsyncGenerator[Organisation, None]:
    if await organisations_repo.get() is None:
        user_input = user_input_generator.new_user_input()
        team_input = TeamInput(name=user_input['team_name'], fullname=user_input['team_name'])
        await organisations_repo.create(team_input)
        await organisations_repo.update_seen()

    organisation = await organisations_repo.get()
    yield organisation

@pytest_asyncio.fixture(scope='session')
async def ontologies_repo(neo4j_tx) -> AsyncGenerator[Neo4jOntologyRepository, None]:
    yield Neo4jOntologyRepository(neo4j_tx)

@pytest_asyncio.fixture(scope='session')
async def ontology(ontologies_repo) -> AsyncGenerator[Ontology, None]:
    ontology = await ontologies_repo.get()
    if not ontology:
        ontology = await ontologies_repo.create()
    yield ontology

@pytest_asyncio.fixture(scope='session')
async def tree_subject(ontology, ontologies_repo) -> AsyncGenerator[Subject, None]:
    if ontology.get_entry(entry="Tree", label="Subject") is None:
        subject = Subject(
             name='Tree',
             description='Trees have roots and leaves'
         )
        ontology.add_entry(subject)
        await ontologies_repo.update_seen()

    _, subject = ontology.get_entry(entry="Tree", label="Subject")
    yield subject

@pytest_asyncio.fixture(scope='session')
async def country_type(ontology, ontologies_repo) -> AsyncGenerator[LocationType, None]:
    if ontology.get_entry(entry="Country", label="LocationType") is None:
        country_type = LocationType(
             name='Country',
             description='Country and three digit code according to ISO 3166-1 alpha-3'
         )
        ontology.add_entry(country_type)
        await ontologies_repo.update_seen()

    _, country_type = ontology.get_entry(entry="Country", label="LocationType")
    yield country_type

@pytest_asyncio.fixture(scope='session')
async def state_type(ontology, ontologies_repo) -> AsyncGenerator[LocationType, None]:
    if ontology.get_entry(entry="State", label="LocationType") is None:
        state_type = LocationType(
             name='State',
             synonyms=['Department', 'County'],
             description='Political subdivision of a country'
         )
        ontology.add_entry(state_type)
        await ontologies_repo.update_seen()
    _, state_type = ontology.get_entry(entry="State", label="LocationType")
    yield state_type

@pytest_asyncio.fixture(scope='session')
async def field_type(ontology, ontologies_repo) -> AsyncGenerator[LocationType, None]:
    if ontology.get_entry(entry="Field", label="LocationType") is None:
        field_type = LocationType(
             name='Field',
             synonyms=['Farm', 'Plot'],
             description='Cultivated area of land'
         )
        ontology.add_entry(field_type)
        await ontologies_repo.update_seen()

    _, field_type = ontology.get_entry(entry="Field", label="LocationType")
    yield field_type

@pytest_asyncio.fixture(scope='session')
async def row_layout_type(ontology, ontologies_repo) -> AsyncGenerator[LayoutType, None]:
    if ontology.get_entry(entry="Rows", label="LayoutType") is None:
        row_layout_type = LayoutType(
            name="Rows",
            synonyms=['Drills'],
            description="Position described by a row number then a count from start of row",
            axes=[AxisType.ORDINAL, AxisType.ORDINAL]
        )
        ontology.add_entry(row_layout_type)
        await ontologies_repo.update_seen()

    _, row_layout_type = ontology.get_entry(entry="Rows", label="LayoutType")
    yield row_layout_type

@pytest_asyncio.fixture(scope='session')
async def grid_layout_type(ontology, ontologies_repo) -> AsyncGenerator[LayoutType, None]:
    if ontology.get_entry(entry="grid", label="LayoutType") is None:
        grid_type = LayoutType(
            name='Grid',
            synonyms=['2D matrix'],
            description='A matrix arrangement of 2-dimensions',
            axes=[AxisType.CARTESIAN, AxisType.CARTESIAN]
         )
        ontology.add_entry(grid_type)
        await ontologies_repo.update_seen()

    _, grid_layout_type = ontology.get_entry(entry="grid", label="LayoutType")
    yield grid_layout_type

@pytest_asyncio.fixture(scope='session')
async def height_trait(ontology, ontologies_repo, tree_subject) -> AsyncGenerator[Trait, None]:
    if ontology.get_entry(entry="Height", label="Trait") is None:
        trait = Trait(name="Height", synonyms=["hauteur"], description="Distance from the ground level to the top")
        ontology.add_entry(trait, subjects=[tree_subject.id])
        await ontologies_repo.update_seen()

    _, height_trait = ontology.get_entry(entry="Height", label="Trait")
    yield height_trait

@pytest_asyncio.fixture(scope='session')
async def cm_scale(ontology, ontologies_repo) -> AsyncGenerator[Scale, None]:
    if ontology.get_entry(entry="cm", label="Scale") is None:
        scale = Scale(name="cm", synonyms=["centimeters"], description="centimetres scale", scale_type=ScaleType.NUMERICAL)
        ontology.add_entry(scale)
        await ontologies_repo.update_seen()

    _, scale = ontology.get_entry(entry="centimeters", label="Scale")
    yield scale

@pytest_asyncio.fixture(scope='session')
async def tape_method(ontology, ontologies_repo) -> AsyncGenerator[ObservationMethod, None]:
    if ontology.get_entry(entry="tape", label="ObservationMethod") is None:
        method = ObservationMethod(
            name="tape",
            synonyms=["tape-measure, ruler"],
            description="measurement against a known length reference",
            observation_type=ObservationMethodType.MEASUREMENT
        )
        ontology.add_entry(method)
        await ontologies_repo.update_seen()

    _, method = ontology.get_entry(entry="tape", label="ObservationMethod")
    yield method

@pytest_asyncio.fixture(scope='session')
async def height_variable(ontology, ontologies_repo, height_trait, cm_scale, tape_method) -> AsyncGenerator[Variable, None]:
    if ontology.get_entry(entry="Height", label="Variable") is None:
        variable = Variable(name="Height", synonyms=["hauteur"], description="Height from the ground")
        ontology.add_entry(variable, trait=height_trait.id, scale=cm_scale.id, method=tape_method.id)
        await ontologies_repo.update_seen()

    _, variable = ontology.get_entry(entry="Height", label="Variable")
    yield variable

@pytest_asyncio.fixture(scope='session')
async def regions_repo(neo4j_tx, stored_account, stored_organisation, test_controllers_service) -> AsyncGenerator[Neo4jRegionsRepository, None]:
    yield Neo4jRegionsRepository(
        neo4j_tx,
        controllers_service=test_controllers_service,
        user_id=stored_account.user.id,
        access_teams={
            Access.READ: [stored_organisation.root.id],
            Access.WRITE: [stored_organisation.root.id],
            Access.ADMIN: [stored_organisation.root.id],
            Access.CURATE: [stored_organisation.root.id]
        }
    )

@pytest_asyncio.fixture(scope='session')
async def example_region(regions_repo, read_model, country_type) -> AsyncGenerator[Region, None]:
    async for c in countries(read_model):
        if isinstance(c, LocationInput):
            country_input = c
            break
    else:
        raise ValueError('No input LocationInputs found in read model countries')
    stored: Region = await regions_repo.create(country_input)
    yield stored

@pytest_asyncio.fixture(scope='session')
async def state_location(regions_repo, example_region, state_type) -> AsyncGenerator[LocationStored, None]:
    state_input = LocationInput(name="Sunshine State", type=state_type.id)
    example_region.add_location(state_input, parent_id = example_region.root.id)
    await regions_repo.update_seen()
    yield example_region.get_location("Sunshine State")

@pytest_asyncio.fixture(scope='session')
async def field_location(regions_repo, example_region, state_location, field_type) -> AsyncGenerator[LocationStored, None]:
    field_input = LocationInput(name="Big Field", type=field_type.id)
    example_region.add_location(field_input, parent_id = state_location.id)
    await regions_repo.update_seen()
    yield example_region.get_location("Big Field")

@pytest_asyncio.fixture(scope='session')
async def arrangements_repo(neo4j_tx, stored_account, stored_organisation, test_controllers_service) -> AsyncGenerator[Neo4jArrangementsRepository, None]:
    yield Neo4jArrangementsRepository(
        neo4j_tx,
        controllers_service=test_controllers_service,
        user_id=stored_account.user.id,
        access_teams={
            Access.READ: [stored_organisation.root.id],
            Access.WRITE: [stored_organisation.root.id],
            Access.CURATE: [stored_organisation.root.id],
            Access.ADMIN: [stored_organisation.root.id]
        }
    )

@pytest_asyncio.fixture(scope='session')
async def example_arrangement(arrangements_repo, row_layout_type, field_location) -> AsyncGenerator[Arrangement, None]:
    new_layout = LayoutInput(
        name="Big field layout 2010",
        type=row_layout_type.id, axes=["row", "number"],
        location=field_location.id
    )
    yield await arrangements_repo.create(new_layout)

@pytest_asyncio.fixture(scope='session')
async def germplasm_repo(neo4j_tx, stored_account, stored_organisation, test_controllers_service,) -> AsyncGenerator[Neo4jGermplasmRepository, None]:
    yield Neo4jGermplasmRepository(
        neo4j_tx,
        controllers_service=test_controllers_service,
        user_id=stored_account.user.id,
        access_teams={
            Access.READ: [stored_organisation.root.id],
            Access.WRITE: [stored_organisation.root.id],
            Access.CURATE: [stored_organisation.root.id],
            Access.ADMIN: [stored_organisation.root.id]
        }
    )

@pytest_asyncio.fixture(scope='session')
async def crossing_method(ontology, ontologies_repo) -> AsyncGenerator[GermplasmMethod, None]:
    if ontology.get_entry(entry="Crossing", label="GermplasmMethod") is None:
        crossing_method = GermplasmMethod(
             name='Crossing',
             synonyms=['Cross', 'Cross-fertilization, Cross-pollination', 'Hybridization', 'Hybridisation'],
             description='Crossing of two distinct varieties to form a hybrid'
         )
        ontology.add_entry(crossing_method)
        await ontologies_repo.update_seen()

    _, crossing_method = ontology.get_entry(entry="Crossing", label="GermplasmMethod")
    yield crossing_method

@pytest_asyncio.fixture(scope='session')
async def references_repo(neo4j_tx, stored_account, stored_organisation, test_controllers_service) -> AsyncGenerator[Neo4jReferencesRepository, None]:
    yield Neo4jReferencesRepository(
        neo4j_tx,
        controllers_service=test_controllers_service,
        user_id=stored_account.user.id,
        access_teams={
            Access.READ: [stored_organisation.root.id],
            Access.WRITE: [stored_organisation.root.id],
            Access.CURATE: [stored_organisation.root.id],
            Access.ADMIN: [stored_organisation.root.id]
        }
    )

@pytest_asyncio.fixture(scope='session')
async def example_external_reference(references_repo) -> AsyncGenerator[ExternalReferenceStored, None]:
    external_reference = ExternalReferenceInput(
        description="Example external reference",
        url="www.example.com",
        external_id="example_id"
    )
    yield await references_repo.create(external_reference)

@pytest_asyncio.fixture(scope='session')
async def example_germplasm(germplasm_repo, example_external_reference) -> AsyncGenerator[Germplasm, None]:
    new_entry = GermplasmEntryInput(
        name="Coffee",
        synonyms=["Coffea spp."],
        description="The genus coffea",
        references=[example_external_reference.id]
    )
    germplasm = await germplasm_repo.create(new_entry)
    yield germplasm

@pytest_asyncio.fixture(scope='session')
async def example_variety(
        germplasm_repo,
        example_germplasm,
        example_external_reference,
        crossing_method,
        example_region
) -> AsyncGenerator[GermplasmEntryStored, None]:
    new_entry = GermplasmEntryInput(
        name="New variety",
        synonyms=["New hybrid"],
        description="A new hybrid variety",
        reproduction= Reproduction.CLONAL,
        origin=example_region.root.id,
        time='1990',
        methods=[crossing_method.id],
        references=[example_external_reference.id]
    )
    example_germplasm.add_entry(new_entry, sources = {example_germplasm.get_root_id(): None})
    await germplasm_repo.update_seen()
    yield example_germplasm.get_entry(entry="New variety")

@pytest_asyncio.fixture(scope='session')
async def blocks_repo(neo4j_tx, stored_account, stored_organisation, test_controllers_service) -> AsyncGenerator[Neo4jBlocksRepository, None]:
    yield Neo4jBlocksRepository(
        neo4j_tx,
        controllers_service=test_controllers_service,
        user_id=stored_account.user.id,
        access_teams={
            Access.READ: [stored_organisation.root.id],
            Access.WRITE: [stored_organisation.root.id],
            Access.CURATE: [stored_organisation.root.id],
            Access.ADMIN: [stored_organisation.root.id]
        }
    )

@pytest_asyncio.fixture(scope="session")
async def tree_block(
        blocks_repo,
        example_variety,
        tree_subject,
        field_location,
        example_arrangement
):
    new_unit = UnitInput(
        subject=tree_subject.id,
        name="First Tree",
        synonyms=['1st tree'],
        description="The first tree planted",
        positions=[
            Position(
                location=field_location.id,
                layout=example_arrangement.root.id,
                coordinates=["1","1"],
                start="2010"
            )
        ]
    )
    yield await blocks_repo.create(new_unit)

@pytest_asyncio.fixture(scope="session")
async def second_tree_block(
        blocks_repo,
        example_variety,
        tree_subject,
        field_location,
        example_arrangement
):
    new_unit = UnitInput(
        subject=tree_subject.id,
        name="Second Tree",
        synonyms=['2nd tree'],
        description="The second tree planted",
        positions=[
            Position(
                location=field_location.id,
                layout=example_arrangement.root.id,
                coordinates=["1","2"],
                start="2010"
            )
        ]
    )
    yield await blocks_repo.create(new_unit)

@pytest_asyncio.fixture(scope='session')
async def programs_repo(neo4j_tx, stored_account, stored_organisation, test_controllers_service) -> AsyncGenerator[Neo4jProgramsRepository, None]:
    yield Neo4jProgramsRepository(
        neo4j_tx,
        controllers_service=test_controllers_service,
        user_id=stored_account.user.id,
        access_teams={
            Access.READ: [stored_organisation.root.id],
            Access.WRITE: [stored_organisation.root.id],
            Access.CURATE: [stored_organisation.root.id],
            Access.ADMIN: [stored_organisation.root.id]
        }
    )

@pytest_asyncio.fixture(scope='session')
async def people_repo(neo4j_tx, stored_account, stored_organisation, test_controllers_service) -> AsyncGenerator[Neo4jPeopleRepository, None]:
    yield Neo4jPeopleRepository(
        neo4j_tx,
        controllers_service=test_controllers_service,
        user_id=stored_account.user.id,
        access_teams={
            Access.READ: [stored_organisation.root.id],
            Access.WRITE: [stored_organisation.root.id],
            Access.CURATE: [stored_organisation.root.id],
            Access.ADMIN: [stored_organisation.root.id]
        }
    )

@pytest_asyncio.fixture(scope='session')
async def stored_person(people_repo, user_input_generator):
    user_input = user_input_generator.new_user_input()
    person_input = PersonInput(name=user_input['name'])
    yield await people_repo.create(person_input)

@pytest_asyncio.fixture(scope='session')
async def datasets_repo(neo4j_tx, test_controllers_service, stored_account, stored_organisation) -> AsyncGenerator[Neo4jDatasetsRepository, None]:
    yield Neo4jDatasetsRepository(
        neo4j_tx,
        controllers_service=test_controllers_service,
        user_id=stored_account.user.id,
        access_teams={
            Access.READ: [stored_organisation.root.id],
            Access.WRITE: [stored_organisation.root.id],
            Access.CURATE: [stored_organisation.root.id],
            Access.ADMIN: [stored_organisation.root.id]
        }
    )

@pytest_asyncio.fixture(scope='session')
async def stored_dataset(datasets_repo, tree_block, height_variable, stored_person, example_external_reference) -> AsyncGenerator[DataSetStored, None]:
    dataset_input = DataSetInput(
        term=height_variable.id,
        contributors=[stored_person.id],
        references=[example_external_reference.id],
        records=[DataRecordInput(unit= tree_block.root.id, value="100", start='2010')]
    )
    stored_dataset = await datasets_repo.create(dataset_input)
    yield stored_dataset
