import uuid

import pytest
from src.breedgraph.domain.model.controls import ReadRelease
from src.breedgraph.domain.model.organisations import Access
from src.breedgraph.domain.model.references import (
    ExternalReferenceInput,
    FileReferenceInput,
    DataExternalInput,
    DataFileInput,
    LegalReferenceInput,

    ExternalReferenceStored,
    FileReferenceStored,
    DataExternalStored,
    DataFileStored,
    LegalReferenceStored
)

from src.breedgraph.adapters.repositories.references import Neo4jReferencesRepository

from src.breedgraph.custom_exceptions import NoResultFoundError, UnauthorisedOperationError

def get_external_reference_input(lorem_text_generator):
    return ExternalReferenceInput(
        description=lorem_text_generator.new_text(20),
        url="www.test.com",
        external_id=lorem_text_generator.new_text(5)
    )

def get_file_reference_input(lorem_text_generator):
    return FileReferenceInput(
        description=lorem_text_generator.new_text(20),
        filename=lorem_text_generator.new_text(5),
        uuid=uuid.uuid4()
    )

@pytest.mark.asyncio(scope="session")
async def test_create_and_get(
        neo4j_tx,
        test_controllers_service,
        stored_account,
        stored_organisation,
        lorem_text_generator
):
    repo = Neo4jReferencesRepository(
        neo4j_tx,
        controllers_service=test_controllers_service,
        user_id=stored_account.user.id,
        access_teams={
            Access.READ: {stored_organisation.root.id},
            Access.WRITE: {stored_organisation.root.id}
        }
    )
    ref_input = get_external_reference_input(lorem_text_generator)
    stored_ref: ExternalReferenceStored = await repo.create(ref_input)
    retrieved_ref: ExternalReferenceStored = await repo.get(reference_id = stored_ref.id)
    assert retrieved_ref.description == retrieved_ref.description
    async for ref in repo.get_all():
        if ref.url == ref_input.url:
            break
    else:
        raise NoResultFoundError("Couldn't find created reference by url in get all")


@pytest.mark.asyncio(scope="session")
async def test_edit_reference(neo4j_tx, test_controllers_service, stored_account, stored_organisation, lorem_text_generator):
    repo = Neo4jReferencesRepository(
        neo4j_tx,
        controllers_service=test_controllers_service,
        user_id=stored_account.user.id,
        access_teams={
            Access.READ: {stored_organisation.root.id},
            Access.WRITE: {stored_organisation.root.id},
            Access.CURATE: {stored_organisation.root.id}
        }
    )
    reference = await repo.get(reference_id=1)
    reference.description = lorem_text_generator.new_text(5)
    await repo.update_seen()
    changed_reference = await repo.get(reference_id=1)
    assert changed_reference.description == reference.description

@pytest.mark.asyncio(scope="session")
async def test_file_reference(neo4j_tx, test_controllers_service, stored_account, stored_organisation, lorem_text_generator):
    repo = Neo4jReferencesRepository(
        neo4j_tx,
        controllers_service=test_controllers_service,
        user_id=stored_account.user.id,
        access_teams= {
            Access.READ: {stored_organisation.root.id},
            Access.WRITE: {stored_organisation.root.id},
            Access.CURATE: {stored_organisation.root.id}
        }
    )
    reference_input = get_file_reference_input(lorem_text_generator)
    stored_ref: FileReferenceStored = await repo.create(reference_input)
    retrieved_ref: FileReferenceStored = await repo.get(reference_id=stored_ref.id)
    assert retrieved_ref.uuid == retrieved_ref.uuid

