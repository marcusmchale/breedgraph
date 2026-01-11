import pytest
from pathlib import Path
import asyncio

from src.breedgraph.domain.model.references import (
    LegalReferenceInput, LegalReferenceStored,
    FileReferenceInput, FileReferenceStored
)
from src.breedgraph.config import FILE_STORAGE_PATH
from tests.e2e.references.post_methods import post_to_create_legal_reference, post_to_create_file_reference
from tests.e2e.utils import get_verified_payload, assert_payload_success

@pytest.mark.usefixtures("session_database")
@pytest.mark.asyncio(scope="session")
async def test_create_legal(
        client,
        first_user_login_token,
        first_account_with_all_affiliations
):
    legal_ref = LegalReferenceInput(
        description="This is a test legal reference",
        text="This is the actual text of the legal reference"
    ).model_dump()
    create_legal_response = await post_to_create_legal_reference(client, token=first_user_login_token, reference=legal_ref)
    legal_payload = get_verified_payload(create_legal_response, "referencesCreateLegal")
    assert_payload_success(legal_payload)

@pytest.mark.usefixtures("session_database")
@pytest.mark.asyncio(scope="session")
async def test_create_file(
        client,
        first_user_login_token,
        first_account_with_all_affiliations
):
    # 1. Create a dummy file in memory
    test_file_content = b"fake file content2"
    test_file_path = Path(FILE_STORAGE_PATH, "test_document.pdf")
    test_file_path.write_bytes(test_file_content)

    with test_file_path.open("rb") as test_file:
        file_reference = {
            'description': 'Test file upload',
            'file': test_file
        }

        create_file_response = await post_to_create_file_reference(
            client,
            token=first_user_login_token,
            reference=file_reference
        )

    file_payload = get_verified_payload(create_file_response, "referencesCreateFile")
    assert_payload_success(file_payload)
    # now verify the file contents
    key = file_payload.get('result')
    file_path = Path(FILE_STORAGE_PATH, key)

    max_retries = 10
    for i in range(max_retries):
        if file_path.exists() and file_path.stat().st_size == len(test_file_content):
            break
        await asyncio.sleep(0.2)

    assert file_path.exists(), f"File key not found after {max_retries} retries"
    file_content = file_path.read_bytes()
    assert len(file_content) > 0, f"File {key} is empty"
    assert file_content == test_file_content
