from numpy import datetime64
from typing import AsyncGenerator

import pytest_asyncio

from src.breedgraph.service_layer.queries.read_models import regions
from src.breedgraph.adapters.neo4j import (
    # services
    Neo4jGermplasmPersistenceService,
    Neo4jOntologyPersistenceService,
    Neo4jAccessControlService,
    # Repositories
    Neo4jAccountRepository,
    Neo4jOrganisationsRepository,
    Neo4jRegionsRepository,
    Neo4jArrangementsRepository,
    Neo4jBlocksRepository,
    Neo4jPeopleRepository,
    Neo4jProgramsRepository,
    Neo4jReferencesRepository,
    Neo4jDatasetsRepository,
)

from src.breedgraph.service_layer.application import OntologyApplicationService, GermplasmApplicationService
from tests.integration.repositories.test_accounts_repository import create_account_input

from src.breedgraph.domain.model.germplasm import (
    GermplasmInput,
    GermplasmStored,
    Reproduction,
    GermplasmRelationship,
    GermplasmSourceType
)
from src.breedgraph.domain.model.accounts import AccountStored
from src.breedgraph.domain.model.organisations import Organisation, TeamInput
from src.breedgraph.domain.model.arrangements import Arrangement, LayoutInput
from src.breedgraph.domain.model.organisations import Access, Affiliation, Authorisation
from src.breedgraph.domain.model.blocks import UnitInput, Position
from src.breedgraph.domain.model.ontology import *
from src.breedgraph.domain.model.people import PersonInput
from src.breedgraph.domain.model.references import ExternalReferenceInput, ExternalReferenceStored
from src.breedgraph.domain.model.regions import LocationInput, LocationStored, Region
from src.breedgraph.domain.model.datasets import DataSetInput, DataSetStored, DataRecordInput

@pytest_asyncio.fixture(scope="session")
async def accounts_repo(uncommitted_neo4j_tx) -> AsyncGenerator[Neo4jAccountRepository, None]:
    yield Neo4jAccountRepository(uncommitted_neo4j_tx)

@pytest_asyncio.fixture(scope="session")
async def first_unstored_account(accounts_repo, user_input_generator) -> AsyncGenerator[AccountStored, None]:
    account_input = await create_account_input(user_input_generator)

    yield await accounts_repo.create(account_input)

@pytest_asyncio.fixture(scope="session")
async def second_unstored_account(accounts_repo, user_input_generator) -> AsyncGenerator[AccountStored, None]:
    account_input = await create_account_input(user_input_generator)
    yield await accounts_repo.create(account_input)

@pytest_asyncio.fixture(scope='session')
async def ontology_persistence_service(uncommitted_neo4j_tx) -> AsyncGenerator[Neo4jOntologyPersistenceService, None]:
    yield Neo4jOntologyPersistenceService(uncommitted_neo4j_tx)

@pytest_asyncio.fixture(scope='session')
async def ontology_service(ontology_persistence_service, first_unstored_account) -> AsyncGenerator[OntologyApplicationService, None]:
    yield OntologyApplicationService(
        ontology_persistence_service,
        user_id=first_unstored_account.user.id,
        role=first_unstored_account.user.ontology_role
    )

@pytest_asyncio.fixture(scope='session')
async def organisations_repo(uncommitted_neo4j_tx, first_unstored_account) -> AsyncGenerator[Neo4jOrganisationsRepository, None]:
    yield Neo4jOrganisationsRepository(uncommitted_neo4j_tx, user_id=first_unstored_account.user.id)

@pytest_asyncio.fixture(scope="session")
async def first_unstored_organisation(user_input_generator, organisations_repo) -> AsyncGenerator[Organisation, None]:
    user_input = user_input_generator.new_user_input()
    team_input = TeamInput(name=user_input['team_name'], fullname=user_input['team_name'])
    yield await organisations_repo.create(team_input)

@pytest_asyncio.fixture(scope="session")
async def first_unstored_account_with_all_access(first_unstored_account, first_unstored_organisation, organisations_repo):
    team = first_unstored_organisation.root
    team.affiliations.set_by_access(
        Access.READ,
        first_unstored_account.user.id,
        Affiliation(authorisation=Authorisation.AUTHORISED, heritable=True)
    )
    team.affiliations.set_by_access(
        Access.WRITE,
        first_unstored_account.user.id,
        Affiliation(authorisation=Authorisation.AUTHORISED, heritable=True)
    )
    team.affiliations.set_by_access(
        Access.CURATE,
        first_unstored_account.user.id,
        Affiliation(authorisation=Authorisation.AUTHORISED, heritable=True)
    )
    await organisations_repo.update_seen()
    yield first_unstored_account

@pytest_asyncio.fixture(scope='session')
async def country_type(ontology_service) -> AsyncGenerator[LocationTypeStored, None]:
    country_type = await ontology_service.get_entry(name="Country", label=OntologyEntryLabel.LOCATION_TYPE)
    if country_type is None:
        country_type = LocationTypeInput(
             name='Country',
             description='Country and three digit code according to ISO 3166-1 alpha-3'
         )
        country_type = await ontology_service.create_entry(country_type)
    yield country_type

@pytest_asyncio.fixture(scope="session")
async def neo4j_access_control_service(uncommitted_neo4j_tx, first_unstored_account_with_all_access) -> AsyncGenerator[Neo4jAccessControlService, None]:
    """Test controllers service fixture for integration tests"""
    access_control_service = Neo4jAccessControlService(tx=uncommitted_neo4j_tx)
    await access_control_service.initialize_user_context(user_id = first_unstored_account_with_all_access.user.id)
    yield access_control_service

@pytest_asyncio.fixture(scope='session')
async def regions_repo(uncommitted_neo4j_tx, neo4j_access_control_service) -> AsyncGenerator[Neo4jRegionsRepository, None]:
    yield Neo4jRegionsRepository(
        uncommitted_neo4j_tx,
        access_control_service=neo4j_access_control_service
    )

@pytest_asyncio.fixture(scope='session')
async def example_region(regions_repo, read_model, country_type) -> AsyncGenerator[Region, None]:
    async for c in regions.countries(read_model):
        if isinstance(c, LocationInput):
            country_input = c
            break
    else:
        raise ValueError('No input LocationInputs found in read model countries')
    stored: Region = await regions_repo.create(country_input)
    yield stored

@pytest_asyncio.fixture(scope='session')
async def germplasm_persistence_service(uncommitted_neo4j_tx, neo4j_access_control_service, ) -> AsyncGenerator[Neo4jGermplasmPersistenceService, None]:
    yield Neo4jGermplasmPersistenceService(uncommitted_neo4j_tx)

@pytest_asyncio.fixture(scope='session')
async def germplasm_service(
        germplasm_persistence_service,
        neo4j_access_control_service,
) -> AsyncGenerator[GermplasmApplicationService, None]:
    yield GermplasmApplicationService(
        persistence_service=germplasm_persistence_service,
        access_control_service=neo4j_access_control_service
    )

@pytest_asyncio.fixture(scope='session')
async def example_crop(
        germplasm_service,
        example_region
) -> AsyncGenerator[GermplasmStored, None]:
    new_entry = GermplasmInput(
        name="Example Crop",
        synonyms=["Coffee"],
        description="Coffea genus, including arabica, canephora etc.",
        origin=example_region.root.id
    )
    yield await germplasm_service.create_entry(new_entry)

@pytest_asyncio.fixture(scope='session')
async def tree_subject(ontology_service) -> AsyncGenerator[SubjectStored, None]:
    if await ontology_service.get_entry(name="Tree", label=OntologyEntryLabel.SUBJECT) is None:
        subject = SubjectInput(
             name='Tree',
             description='Trees have roots and leaves'
         )
        await ontology_service.create_entry(subject)

    subject = await ontology_service.get_entry(name="Tree", label=OntologyEntryLabel.SUBJECT)
    yield subject

@pytest_asyncio.fixture(scope='session')
async def state_type(ontology_service, country_type) -> AsyncGenerator[LocationTypeStored, None]:
    state_type = await ontology_service.get_entry(name="State", label=OntologyEntryLabel.LOCATION_TYPE)
    if state_type is None:
        state_type = LocationTypeInput(
             name='State',
             synonyms=['Department', 'County'],
             description='Political subdivision of a country'
         )
        state_type = await ontology_service.create_entry(state_type, parents=[country_type.id])
    yield state_type

@pytest_asyncio.fixture(scope='session')
async def field_type(ontology_service) -> AsyncGenerator[LocationTypeStored, None]:
    if await ontology_service.get_entry(name="Field", label=OntologyEntryLabel.LOCATION_TYPE) is None:
        field_type = LocationTypeInput(
             name='Field',
             synonyms=['Farm', 'Plot'],
             description='Cultivated area of land'
         )
        await ontology_service.create_entry(field_type)

    field_type = await ontology_service.get_entry(name="Field", label=OntologyEntryLabel.LOCATION_TYPE)
    yield field_type

@pytest_asyncio.fixture(scope='session')
async def row_layout_type(ontology_service) -> AsyncGenerator[LayoutTypeStored, None]:
    if await ontology_service.get_entry(name="Rows", label=OntologyEntryLabel.LAYOUT_TYPE) is None:
        row_layout_type = LayoutTypeInput(
            name="Rows",
            synonyms=['Drills'],
            description="Position described by a row number then a count from start of row",
            axes=[AxisType.ORDINAL, AxisType.ORDINAL]
        )
        await ontology_service.create_entry(row_layout_type)

    row_layout_type = await ontology_service.get_entry(name="Rows", label=OntologyEntryLabel.LAYOUT_TYPE)
    yield row_layout_type

@pytest_asyncio.fixture(scope='session')
async def grid_layout_type(ontology_service) -> AsyncGenerator[LayoutTypeStored, None]:
    if await ontology_service.get_entry(name="grid", label=OntologyEntryLabel.LAYOUT_TYPE) is None:
        grid_type = LayoutTypeInput(
            name='Grid',
            synonyms=['2D matrix'],
            description='A matrix arrangement of 2-dimensions',
            axes=[AxisType.CARTESIAN, AxisType.CARTESIAN]
         )
        await ontology_service.create_entry(grid_type)

    grid_layout_type = await ontology_service.get_entry(name="grid", label=OntologyEntryLabel.LAYOUT_TYPE)
    yield grid_layout_type

@pytest_asyncio.fixture(scope='session')
async def height_trait(uncommitted_neo4j_tx, ontology_service, tree_subject) -> AsyncGenerator[TraitStored, None]:
    if await ontology_service.get_entry(name="Height", label=OntologyEntryLabel.TRAIT) is None:
        trait = TraitInput(name="Height", synonyms=["hauteur"], description="Distance from the ground level to the top")
        await ontology_service.create_trait(trait, subjects=[tree_subject.id])

    height_trait = await ontology_service.get_entry(name="Height", label=OntologyEntryLabel.TRAIT)
    yield height_trait

@pytest_asyncio.fixture(scope='session')
async def cm_scale(ontology_service) -> AsyncGenerator[ScaleStored, None]:
    if await ontology_service.get_entry(name="cm", label=OntologyEntryLabel.SCALE) is None:
        scale = ScaleInput(name="cm", synonyms=["centimeters"], description="centimetres scale", scale_type=ScaleType.NUMERICAL)
        await ontology_service.create_entry(scale)

    scale = await ontology_service.get_entry(name="cm", label=OntologyEntryLabel.SCALE)
    yield scale

@pytest_asyncio.fixture(scope='session')
async def tape_method(ontology_service) -> AsyncGenerator[ObservationMethodStored, None]:
    if await ontology_service.get_entry(name="tape", label=OntologyEntryLabel.OBSERVATION_METHOD) is None:
        method = ObservationMethodInput(
            name="tape",
            synonyms=["tape-measure, ruler"],
            description="measurement against a known length reference",
            observation_type=ObservationMethodType.MEASUREMENT
        )
        await ontology_service.create_entry(method)

    method = await ontology_service.get_entry(name="tape", label=OntologyEntryLabel.OBSERVATION_METHOD)
    yield method

@pytest_asyncio.fixture(scope='session')
async def height_variable(ontology_service, height_trait, cm_scale, tape_method) -> AsyncGenerator[VariableStored, None]:
    if await ontology_service.get_entry(name="Height", label=OntologyEntryLabel.VARIABLE) is None:
        variable = VariableInput(name="Height", synonyms=["hauteur"], description="Height from the ground")
        await ontology_service.create_variable(variable, trait_id=height_trait.id, scale_id=cm_scale.id, observation_method_id=tape_method.id)

    variable = await ontology_service.get_entry(name="Height", label=OntologyEntryLabel.VARIABLE)
    yield variable

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
async def arrangements_repo(uncommitted_neo4j_tx, first_unstored_account, stored_organisation, neo4j_access_control_service) -> AsyncGenerator[Neo4jArrangementsRepository, None]:
    yield Neo4jArrangementsRepository(
        uncommitted_neo4j_tx,
        access_control_service=neo4j_access_control_service,
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
async def crossing_method(ontology_service) -> AsyncGenerator[ControlMethodStored, None]:
    if await ontology_service.get_entry(name="Crossing", label=OntologyEntryLabel.CONTROL_METHOD) is None:
        crossing_method = ControlMethodInput(
             name='Crossing',
             synonyms=['Cross', 'Cross-fertilization, Cross-pollination', 'Hybridization', 'Hybridisation'],
             description='Crossing of two distinct varieties to form a hybrid'
         )
        await ontology_service.create_entry(crossing_method)

    crossing_method = await ontology_service.get_entry(name="Crossing", label=OntologyEntryLabel.CONTROL_METHOD)
    yield crossing_method

@pytest_asyncio.fixture(scope='session')
async def references_repo(uncommitted_neo4j_tx, first_unstored_account, stored_organisation, neo4j_access_control_service) -> AsyncGenerator[Neo4jReferencesRepository, None]:
    yield Neo4jReferencesRepository(
        uncommitted_neo4j_tx,
        access_control_service=neo4j_access_control_service
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
async def example_crop(
        germplasm_service,
        example_region
) -> AsyncGenerator[GermplasmStored, None]:
    new_entry = GermplasmInput(
        name="Coffea spp.",
        synonyms=["Coffee"],
        description="Coffea genus, including arabica, canephora etc.",
        origin=example_region.root.id
    )
    yield await germplasm_service.create_entry(new_entry)


@pytest_asyncio.fixture(scope='session')
async def example_variety(
        germplasm_service,
        example_external_reference,
        crossing_method,
        example_region,
        example_crop
) -> AsyncGenerator[GermplasmStored, None]:
    new_entry = GermplasmInput(
        name="New variety",
        synonyms=["New hybrid"],
        description="A new hybrid variety",
        reproduction= Reproduction.CLONAL,
        origin=example_region.root.id,
        time=datetime64('1990'),
        control_methods=[crossing_method.id],
        references=[example_external_reference.id]
    )
    entry = await germplasm_service.create_entry(new_entry)
    await germplasm_service.create_relationship(GermplasmRelationship(source_id = example_crop.id, sink_id= entry.id))
    yield entry

@pytest_asyncio.fixture(scope='session')
async def blocks_repo(uncommitted_neo4j_tx, neo4j_access_control_service) -> AsyncGenerator[Neo4jBlocksRepository, None]:
    yield Neo4jBlocksRepository(
        uncommitted_neo4j_tx,
        access_control_service=neo4j_access_control_service
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
        description="The first tree planted",
        positions=[
            Position(
                location=field_location.id,
                layout=example_arrangement.root.id,
                coordinates=["1","1"],
                start=datetime64("2010")
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
        description="The second tree planted",
        positions=[
            Position(
                location=field_location.id,
                layout=example_arrangement.root.id,
                coordinates=["1","2"],
                start=datetime64("2010")
            )
        ]
    )
    yield await blocks_repo.create(new_unit)

@pytest_asyncio.fixture(scope='session')
async def programs_repo(uncommitted_neo4j_tx, neo4j_access_control_service) -> AsyncGenerator[Neo4jProgramsRepository, None]:
    yield Neo4jProgramsRepository(
        uncommitted_neo4j_tx,
        access_control_service=neo4j_access_control_service
    )

@pytest_asyncio.fixture(scope='session')
async def people_repo(uncommitted_neo4j_tx, neo4j_access_control_service) -> AsyncGenerator[Neo4jPeopleRepository, None]:
    yield Neo4jPeopleRepository(
        uncommitted_neo4j_tx,
        access_control_service=neo4j_access_control_service
    )

@pytest_asyncio.fixture(scope='session')
async def unstored_person(people_repo, user_input_generator):
    user_input = user_input_generator.new_user_input()
    person_input = PersonInput(name=user_input['name'])
    person_stored = await people_repo.create(person_input)
    yield person_stored

@pytest_asyncio.fixture(scope='session')
async def datasets_repo(uncommitted_neo4j_tx, neo4j_access_control_service) -> AsyncGenerator[Neo4jDatasetsRepository, None]:
    yield Neo4jDatasetsRepository(
        uncommitted_neo4j_tx,
        access_control_service=neo4j_access_control_service
    )

@pytest_asyncio.fixture(scope='session')
async def stored_dataset(datasets_repo, tree_block, height_variable, unstored_person, example_external_reference) -> AsyncGenerator[DataSetStored, None]:
    dataset_input = DataSetInput(
        concept=height_variable.id,
        contributors=[unstored_person.id],
        references=[example_external_reference.id],
        records=[DataRecordInput(unit= tree_block.root.id, value="100", start=datetime64('2010'))]
    )
    stored_dataset = await datasets_repo.create(dataset_input)
    yield stored_dataset
