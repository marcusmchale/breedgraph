import pytest
import pytest_asyncio
from datetime import datetime
from src.breedgraph.domain.model.controls import Control, ReadRelease, Controller
from src.breedgraph.domain.model.regions import Region, LocationInput, LocationStored

from src.breedgraph.adapters.repositories.regions import Neo4jRegionsRepository
from src.breedgraph.adapters.repositories.ontologies import Neo4jOntologyRepository

from src.breedgraph.domain.model.ontology import Ontology, OntologyEntry
from src.breedgraph.domain.model.ontology.locations import Location
from src.breedgraph.domain.model.regions import LocationInput, LocationStored

from src.breedgraph.views.regions import countries

from src.breedgraph.custom_exceptions import NoResultFoundError, UnauthorisedOperationError

@pytest_asyncio.fixture(scope='session')
async def ontologies_repo(neo4j_tx) -> Neo4jOntologyRepository:
    yield Neo4jOntologyRepository(neo4j_tx)

@pytest_asyncio.fixture(scope='session')
async def ontology(ontologies_repo) -> Ontology:
    yield await ontologies_repo.get()

@pytest_asyncio.fixture(scope='session')
async def country_type(ontology, ontologies_repo) -> Location:
    country_type = next(ontology.get(name="Country",label="LocationType"), None)
    if country_type is None:
        country_type = Location(
             name='Country',
             description='Country and three digit code according to ISO 3166-1 alpha-3'
         )
        ontology._add_entry(country_type)
        await ontologies_repo.update_seen()
    yield country_type

@pytest_asyncio.fixture(scope='session')
async def state_type(ontology, ontologies_repo) -> Location:
    state_type = next(ontology.get(name="State", label="LocationType"), None)
    if state_type is None:
        state_type = Location(
             name='State',
             synonyms=['Department', 'County'],
             description='Political subdivision of a country'
         )
        ontology._add_entry(state_type)
        await ontologies_repo.update_seen()
    yield state_type

@pytest_asyncio.fixture(scope='session')
async def field_type(ontology, ontologies_repo) -> Location:
    field_type = next(ontology.get(name="Field", label="LocationType"), None)
    if field_type is None:
        field_type = Location(
             name='Field',
             synonyms=['Farm', 'Plot'],
             description='Cultivated area of land'
         )
        ontology._add_entry(field_type)
        await ontologies_repo.update_seen()
    yield field_type

@pytest.mark.asyncio(scope="session")
async def test_create_from_countries_in_read_model_and_get(
        neo4j_tx,
        stored_account_with_affiliations,
        stored_account_without_affiliations,
        lorem_text_generator,
        read_model,
        country_type
):
    async for c in countries(read_model):
        if isinstance(c, LocationInput):
            country_input = c
            break
    else:
        raise ValueError('No input LocationInputs found in read model countries')
    repo = Neo4jRegionsRepository(neo4j_tx, account=stored_account_with_affiliations)
    control = Control(team=stored_account_with_affiliations.writes[0], release=ReadRelease.PUBLIC)
    country_input.controller.controls.append(control)
    stored: Region = await repo.create(country_input)
    retrieved = await repo.get(member_id = stored.root.id)
    assert stored.root == retrieved.root
    async for l in repo.get_all():
        if stored.root.id == l.root.id:
            break
    else:
        raise AssertionError("couldn't find stored region by get all")

@pytest.mark.asyncio(scope="session")
async def test_extend_region_with_county_aka_state(
        neo4j_tx,
        stored_account_with_affiliations,
        ontology, state_type,
        lorem_text_generator
):
    repo = Neo4jRegionsRepository(neo4j_tx, account=stored_account_with_affiliations)
    region = await anext(repo.get_all())
    control = Control(team=stored_account_with_affiliations.writes[0], release=ReadRelease.PUBLIC)
    county_type = next(ontology.get(name='county'))
    county_input = LocationInput(
        type=county_type.id,
        name=lorem_text_generator.new_text(),
        controller=Controller(controls=[control]), parent=region.root.id
    )
    region._add_node(county_input)
    await repo.update_seen()
    assert region.get_node(name=county_input.name).parent == region.root.id
    assert region.get_node(name=county_input.name).id in region.root.children

#@pytest.mark.asyncio(scope="session")
#async def test_extend_region_with_private_field_location(
#        neo4j_tx,
#        stored_account_with_affiliations,
#        stored_account_without_affiliations,
#        ontology, field_type,
#        lorem_text_generator
#):
#    repo = Neo4jRegionsRepository(neo4j_tx, account=stored_account_with_affiliations)
#    region = await anext(repo.get_all())
#    county = region.members[region.root.children[0]]
#    control = Control(team=stored_account_with_affiliations.writes[0], release=Release.PRIVATE)
#    field_input = LocationInput(
#        type=field_type.id,
#        name=lorem_text_generator.new_text(),
#        controller=EntityController(controls=[control]), parent=county.id
#    )
#    region.add_member(field_input)
#    await repo.update_seen()
#    assert region.get_member(name=field_input.name).parent == county.id
#
#    unaffiliated_repo = Neo4jRegionsRepository(neo4j_tx, account=stored_account_without_affiliations)
#    uregion = await unaffiliated_repo.get(member_id=region.root.id)
#