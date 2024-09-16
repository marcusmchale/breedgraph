import pytest_asyncio

from src.breedgraph.adapters.repositories.accounts import Neo4jAccountRepository
from src.breedgraph.adapters.repositories.arrangements import Neo4jArrangementsRepository
from src.breedgraph.adapters.repositories.germplasms import Neo4jGermplasmRepository
from src.breedgraph.adapters.repositories.organisations import Neo4jOrganisationsRepository
from src.breedgraph.adapters.repositories.references import Neo4jReferencesRepository

from src.breedgraph.domain.model.accounts import AccountStored
from src.breedgraph.domain.model.germplasm import Germplasm, GermplasmEntryInput, Reproduction, GermplasmSourceType
from src.breedgraph.domain.model.layouts import Arrangement, LayoutInput
from src.breedgraph.domain.model.organisations import TeamInput, Organisation

from src.breedgraph.domain.model.ontology import Subject, GermplasmMethod, LocationType, LayoutType
from src.breedgraph.domain.model.references import ExternalReferenceInput, ExternalReferenceStored

from src.breedgraph.views.regions import countries
from src.breedgraph.adapters.repositories.regions import Neo4jRegionsRepository
from src.breedgraph.domain.model.regions import LocationInput, LocationStored, Region



from tests.integration.test_accounts_repository import create_account_input
from tests.integration.test_organisations_repository import create_team_input

@pytest_asyncio.fixture(scope="session")
async def stored_account(user_input_generator, neo4j_tx) -> AccountStored:
    account_input = await create_account_input(user_input_generator)
    accounts_repo = Neo4jAccountRepository(neo4j_tx)
    stored_account: AccountStored = await accounts_repo.create(account_input)
    await accounts_repo.update_seen()
    yield stored_account

@pytest_asyncio.fixture(scope="session")
async def second_account(user_input_generator, neo4j_tx) -> AccountStored:
    account_input = await create_account_input(user_input_generator)
    accounts_repo = Neo4jAccountRepository(neo4j_tx)
    second_account: AccountStored = await accounts_repo.create(account_input)
    await accounts_repo.update_seen()
    yield second_account

@pytest_asyncio.fixture(scope='session')
async def organisations_repo(neo4j_tx, stored_account) -> Neo4jOrganisationsRepository:
    yield Neo4jOrganisationsRepository(neo4j_tx, user_id=stored_account.user.id)

@pytest_asyncio.fixture(scope="session")
async def stored_organisation(user_input_generator, organisations_repo) -> Organisation:
    if await organisations_repo.get() is None:
        user_input = user_input_generator.new_user_input()
        team_input = TeamInput(name=user_input['team_name'], fullname=user_input['team_name'])
        await organisations_repo.create(team_input)
        await organisations_repo.update_seen()

    organisation = await organisations_repo.get()
    yield organisation

@pytest_asyncio.fixture(scope='session')
async def tree_subject(ontology, ontologies_repo) -> Subject:
    if ontology.get_entry(entry="Tree", label="Subject") is None:
        subject = Subject(
             name='Tree',
             description='Trees have roots and leaves'
         )
        ontology.add_subject(subject)
        await ontologies_repo.update_seen()

    _, subject = ontology.get_entry(entry="Tree", label="Subject")
    yield subject

@pytest_asyncio.fixture(scope='session')
async def country_type(ontology, ontologies_repo) -> LocationType:
    if ontology.get_entry(entry="Country", label="LocationType") is None:
        country_type = LocationType(
             name='Country',
             description='Country and three digit code according to ISO 3166-1 alpha-3'
         )
        ontology.add_location(country_type)
        await ontologies_repo.update_seen()

    _, country_type = ontology.get_entry(entry="Country", label="LocationType")
    yield country_type

@pytest_asyncio.fixture(scope='session')
async def state_type(ontology, ontologies_repo) -> LocationType:
    if ontology.get_entry(entry="State", label="LocationType") is None:
        state_type = LocationType(
             name='State',
             synonyms=['Department', 'County'],
             description='Political subdivision of a country'
         )
        ontology.add_location(state_type)
        await ontologies_repo.update_seen()

    _, state_type = ontology.get_entry(entry="State", label="LocationType")
    yield state_type

@pytest_asyncio.fixture(scope='session')
async def field_type(ontology, ontologies_repo) -> LocationType:
    if ontology.get_entry(entry="Field", label="LocationType") is None:
        field_type = LocationType(
             name='Field',
             synonyms=['Farm', 'Plot'],
             description='Cultivated area of land'
         )
        ontology.add_location(field_type)
        await ontologies_repo.update_seen()

    _, field_type = ontology.get_entry(entry="Field", label="LocationType")
    yield field_type

@pytest_asyncio.fixture(scope='session')
async def row_layout_type(ontology, ontologies_repo) -> LayoutType:
    if ontology.get_entry(entry="Rows", label="LayoutType") is None:
        row_layout_type = LayoutType(
            name="Rows",
            synonyms=['Drills'],
            description="Rows position described by a row index then an index from start of row"
        )
        ontology.add_layout(row_layout_type)
        await ontologies_repo.update_seen()

    _, row_layout_type = ontology.get_entry(entry="Rows", label="LayoutType")
    yield row_layout_type

@pytest_asyncio.fixture(scope='session')
async def grid_layout_type(ontology, ontologies_repo) -> LayoutType:
    if ontology.get_entry(entry="grid", label="LayoutType") is None:
        grid_type = LayoutType(
             name='Grid',
             synonyms=['matrix'],
             description='A matrix arrangement of n-dimensions'
         )
        ontology.add_layout(grid_type)
        await ontologies_repo.update_seen()

    _, grid_layout_type = ontology.get_entry(entry="grid", label="LayoutType")
    yield grid_layout_type

@pytest_asyncio.fixture(scope='session')
async def regions_repo(neo4j_tx, stored_account, stored_organisation) -> Neo4jRegionsRepository:
    yield Neo4jRegionsRepository(
        neo4j_tx,
        user_id=stored_account.user.id,
        read_teams=[stored_organisation.root.id],
        write_teams=[stored_organisation.root.id]
    )

@pytest_asyncio.fixture(scope='session')
async def example_region(regions_repo, read_model, country_type) -> Region:
    async for c in countries(read_model):
        if isinstance(c, LocationInput):
            country_input = c
            break
    else:
        raise ValueError('No input LocationInputs found in read model countries')

    stored: Region = await regions_repo.create(country_input)
    yield stored

@pytest_asyncio.fixture(scope='session')
async def state_location(regions_repo, example_region, state_type) -> LocationStored:
    state_input = LocationInput(name="Sunshine State", type=state_type.id)
    example_region.add_location(state_input, parent_id = example_region.root.id)
    await regions_repo.update_seen()
    yield example_region.get_location("Sunshine State")

@pytest_asyncio.fixture(scope='session')
async def field_location(regions_repo, example_region, state_location, field_type) -> LocationStored:
    field_input = LocationInput(name="Big Field", type=field_type.id)
    example_region.add_location(field_input, parent_id = state_location.id)
    await regions_repo.update_seen()
    yield example_region.get_location("Big Field")

@pytest_asyncio.fixture(scope='session')
async def arrangements_repo(neo4j_tx, stored_account, stored_organisation) -> Neo4jArrangementsRepository:
    yield Neo4jArrangementsRepository(
        neo4j_tx,
        user_id=stored_account.user.id,
        read_teams=[stored_organisation.root.id],
        write_teams=[stored_organisation.root.id]
    )

@pytest_asyncio.fixture(scope='session')
async def example_arrangement(arrangements_repo, row_layout_type, field_location) -> Arrangement:
    new_layout = LayoutInput(
        name="Big field layout 2010",
        type=row_layout_type.id, axes=["row", "number"],
        location=field_location.id
    )
    yield await arrangements_repo.create(new_layout)

@pytest_asyncio.fixture(scope='session')
async def germplasm_repo(neo4j_tx, stored_account, stored_organisation) -> Neo4jGermplasmRepository:
    yield Neo4jGermplasmRepository(
        neo4j_tx,
        user_id=stored_account.user.id,
        read_teams=[stored_organisation.root.id],
        write_teams=[stored_organisation.root.id]
    )

@pytest_asyncio.fixture(scope='session')
async def crossing_method(ontology, ontologies_repo) -> GermplasmMethod:
    if ontology.get_entry(entry="Crossing", label="GermplasmMethod") is None:
        crossing_method = GermplasmMethod(
             name='Crossing',
             synonyms=['Cross', 'Cross-fertilization, Cross-pollination', 'Hybridization', 'Hybridisation'],
             description='Crossing of two distinct varieties to form a hybrid'
         )
        ontology.add_germplasm_method(crossing_method)
        await ontologies_repo.update_seen()

    _, crossing_method = ontology.get_entry(entry="Crossing", label="GermplasmMethod")
    yield crossing_method

@pytest_asyncio.fixture(scope='session')
async def references_repo(neo4j_tx, stored_account, stored_organisation) -> Neo4jReferencesRepository:
    return Neo4jReferencesRepository(
        neo4j_tx,
        user_id=stored_account.user.id,
        read_teams=[stored_organisation.root.id],
        write_teams=[stored_organisation.root.id]
    )

@pytest_asyncio.fixture(scope='session')
async def example_external_reference(references_repo) -> ExternalReferenceStored:
    external_reference = ExternalReferenceInput(
        description="Example external reference",
        url="www.example.com",
        external_id="example_id"
    )
    yield await references_repo.create(external_reference)

@pytest_asyncio.fixture(scope='session')
async def example_germplasm(germplasm_repo, example_external_reference) -> Germplasm:
    new_entry = GermplasmEntryInput(
        name="Coffee",
        synonyms=["Coffea spp."],
        description="The genus coffea",
        references=[example_external_reference.id]
    )
    germplasm = await germplasm_repo.create(new_entry)
    yield germplasm

@pytest_asyncio.fixture(scope='session')
async def example_variety(germplasm_repo, example_germplasm, example_external_reference, crossing_method, example_region):
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


