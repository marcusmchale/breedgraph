import pytest
from pathlib import Path
from datetime import datetime
import asyncio

from src.breedgraph.domain.model.references import (
    LegalReferenceInput, LegalReferenceStored,
    FileReferenceInput, FileReferenceStored
)
from src.breedgraph.config import FILE_STORAGE_PATH, get_base_url
from tests.e2e.references.post_methods import (
    post_to_create_legal_reference,
    post_to_create_file_reference,
    post_to_file_submission,
    post_to_file_download
)
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
    test_file_content = b"fake file content"
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


@pytest.mark.usefixtures("session_database")
@pytest.mark.asyncio(scope="session")
async def test_create_monitor_progress_and_get_file(
        client,
        first_user_login_token,
        first_account_with_all_affiliations
):
    # 1. Create a dummy file in memory
    test_file_content = b"fake file content2"
    test_file_path = Path(FILE_STORAGE_PATH, "test_document2.pdf")
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

    #monitor progress
    max_retries = 10
    reference_id = None
    status = None
    for i in range(max_retries):
        file_submission_response = await post_to_file_submission(
            client,
            token=first_user_login_token,
            file_id=key
        )
        file_submission_payload = get_verified_payload(file_submission_response, "referencesFileSubmission")
        assert_payload_success(file_submission_payload)
        file_submission_result = file_submission_payload.get('result')
        status = file_submission_result.get('status')
        if status == 'COMPLETED':
            reference_id = file_submission_result.get('referenceId')
            assert reference_id
            assert not file_submission_result.get('errors')
            assert file_submission_result.get('progress') == 100
            break
        else:
            print(file_submission_result.get('status'), file_submission_result.get('progress'))
        await asyncio.sleep(0.1)
    if not reference_id:
        raise Exception(f"File submission failed with status: {status}")

    # now get the download url and attempt to download the file
    file_download_result = None
    for i in range(max_retries):
        file_download_response = await post_to_file_download(
            client,
            token=first_user_login_token,
            file_id=key
        )
        file_download_payload = get_verified_payload(file_download_response, "referencesFileDownload")
        try:
            if file_download_payload.get('status') == "SUCCESS":
                file_download_result = file_download_payload.get('result')
                break
            else:
                await asyncio.sleep(0.1)
                continue

        except Exception as e:
            print(f"File download failed after {i+1} retries: {e}")

    assert file_download_result.get('filename') == test_file_path.name
    assert file_download_result.get('contentType') == 'application/pdf'
    assert datetime.fromisoformat(file_download_result.get('expiresAt'))
    assert file_download_result.get('token')
    assert file_download_result.get('url')

    # get request to url
    response = await client.get(file_download_result.get('url'))
    file_content = response.content
    assert len(file_content) > 0, f"File {key} is empty"
    assert file_content == test_file_content
