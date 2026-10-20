import pytest
from pathlib import Path
from datetime import datetime
import asyncio

from breedgraph.domain.model.references import (
    LegalReferenceInput
)
from breedgraph.config import FILE_STORAGE_PATH, RETENTION_AUTH_TOKEN, UNUSED_REFERENCE_RETENTION_DAYS
from breedgraph.domain.model.germplasm import GermplasmInput
from neo4j.exceptions import ResultNotSingleError

from breedgraph.domain.model.archive import ArchiveState, LocalState
from tests.breedgraph.e2e.references.post_methods import (
    post_to_create_legal_reference,
    post_to_create_file_reference,
    post_to_update_file_reference,
    post_to_file_submission,
    post_to_file_download
)
from tests.breedgraph.e2e.utils import get_verified_payload, assert_payload_success, with_auth, GQL_API_PATH
from tests.breedgraph.scenarios.person_builder import PersonBuilder
from breedgraph.domain.model.ontology import OntologyEntryLabel

@pytest.mark.asyncio(loop_scope="session")
async def test_create_legal(
        reference_build_context,
        login_token_factory,
        client
):
    user_id = reference_build_context['user_id']
    login_token = login_token_factory(user_id)
    legal_ref = {
        "description": "This is a test legal reference",
        "text": "This is the actual text of the legal reference"
    }
    create_legal_response = await post_to_create_legal_reference(client, token=login_token, reference=legal_ref, control_team_id=reference_build_context['team_id'])
    legal_payload = get_verified_payload(create_legal_response, "referencesCreateLegal")
    assert_payload_success(legal_payload)

@pytest.mark.asyncio(loop_scope="session")
async def test_create_file(
        reference_build_context,
        login_token_factory,
        client,
        uow_factory
):
    user_id = reference_build_context['user_id']
    login_token = login_token_factory(user_id)
    person_id = await PersonBuilder(uow_factory=uow_factory).person(user_id=user_id, team_id=reference_build_context['team_id'])
    async with uow_factory.get_uow(user_id=user_id) as uow:
        analysis = (await uow.ontology.get_entry(name='Formal analysis', label=OntologyEntryLabel.ROLE)).id
    # 1. Create a dummy file in memory
    test_file_content = b"fake file content"
    test_file_path = Path(FILE_STORAGE_PATH, "test_document.pdf")
    test_file_path.write_bytes(test_file_content)

    with test_file_path.open("rb") as test_file:
        file_reference = {
            'description': 'Test file upload',
            'file': test_file,
            'contributions': [{'personId': person_id, 'roleIds': [analysis]}]
        }

        create_file_response = await post_to_create_file_reference(
            client,
            token=login_token,
            reference=file_reference,
            control_team_id=reference_build_context['team_id']
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

    # the file credits the Person, with their role
    async with uow_factory.get_uow(user_id=user_id) as uow:
        reference_id = (await uow.repositories.references.get(file_id=key)).id
    response = await client.post(GQL_API_PATH, json={
        "query": (
            " query ( $ids: [ID!] ) { references( ids: $ids ) { status result { "
            "  ... on FileReference { contributions { person { id } roles { name } } } "
            " } errors { name message } } } "
        ),
        "variables": {"ids": [reference_id]}
    }, headers=with_auth(csrf_token=client.headers["X-CSRF-Token"], auth_token=login_token))
    payload = get_verified_payload(response, "references")
    assert payload['result'][0]['contributions'] == [{'person': {'id': str(person_id)}, 'roles': [{'name': 'Formal analysis'}]}]


@pytest.mark.asyncio(loop_scope="session")
async def test_create_monitor_progress_and_get_file(
        reference_build_context,
        login_token_factory,
        client
):
    user_id = reference_build_context['user_id']
    login_token = login_token_factory(user_id)

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
            token=login_token,
            reference=file_reference,
            control_team_id=reference_build_context['team_id']
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
            token=login_token,
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
            token=login_token,
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

    assert datetime.fromisoformat(file_download_result.get('expiresAt'))
    assert file_download_result.get('url')

    # get request to url
    response = await client.get(file_download_result.get('url'))
    file_content = response.content
    assert len(file_content) > 0, f"File {key} is empty"
    assert file_content == test_file_content


async def wait_for_archival_record(archival_service, file_id: str):
    """ The archival record is created last, once an upload is complete """
    max_retries = 20
    for i in range(max_retries):
        try:
            return await archival_service.get(file_id)
        except ResultNotSingleError:
            await asyncio.sleep(0.2)
    raise AssertionError(f"No archival record for {file_id} after {max_retries} retries")


@pytest.mark.asyncio(loop_scope="session")
async def test_replace_file(
        reference_build_context,
        login_token_factory,
        client,
        uow_factory,
        bus
):
    user_id = reference_build_context['user_id']
    login_token = login_token_factory(user_id)

    first_path = Path(FILE_STORAGE_PATH, "test_document3.pdf")
    first_path.write_bytes(b"first version")
    with first_path.open("rb") as test_file:
        create_file_response = await post_to_create_file_reference(
            client,
            token=login_token,
            reference={'description': 'Test file replacement', 'file': test_file},
            control_team_id=reference_build_context['team_id']
        )
    first_key = get_verified_payload(create_file_response, "referencesCreateFile").get('result')
    await wait_for_archival_record(bus.archival_service, first_key)
    async with uow_factory.get_uow(user_id=user_id) as uow:
        reference_id = (await uow.repositories.references.get(file_id=first_key)).id

    second_path = Path(FILE_STORAGE_PATH, "test_document4.pdf")
    second_path.write_bytes(b"second version")
    with second_path.open("rb") as test_file:
        update_file_response = await post_to_update_file_reference(
            client,
            token=login_token,
            reference={'id': reference_id, 'file': test_file}
        )
    update_payload = get_verified_payload(update_file_response, "referencesUpdateFile")
    assert_payload_success(update_payload)
    second_key = update_payload.get('result')
    second_record = await wait_for_archival_record(bus.archival_service, second_key)

    # the reference points to the new file, which is to be archived
    async with uow_factory.get_uow(user_id=user_id) as uow:
        reference = await uow.repositories.references.get(reference_id=reference_id)
        assert reference.file_id == second_key
        assert reference.filename == "test_document4.pdf"
    assert Path(FILE_STORAGE_PATH, second_key).read_bytes() == b"second version"
    assert second_record.archive_state == ArchiveState.ARCHIVAL_PENDING

    # and the file it replaced is deleted, here and from the archive
    assert not Path(FILE_STORAGE_PATH, first_key).exists()
    first_record = await bus.archival_service.get(first_key)
    assert first_record.local_state == LocalState.EXPIRED
    assert first_record.archive_state == ArchiveState.DELETION_PENDING


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_file_reference(
        reference_build_context,
        login_token_factory,
        client,
        uow_factory,
        bus
):
    user_id = reference_build_context['user_id']
    login_token = login_token_factory(user_id)

    test_file_path = Path(FILE_STORAGE_PATH, "test_document5.pdf")
    test_file_path.write_bytes(b"to be deleted")
    with test_file_path.open("rb") as test_file:
        create_file_response = await post_to_create_file_reference(
            client,
            token=login_token,
            reference={'description': 'Test file deletion', 'file': test_file},
            control_team_id=reference_build_context['team_id']
        )
    key = get_verified_payload(create_file_response, "referencesCreateFile").get('result')
    await wait_for_archival_record(bus.archival_service, key)
    async with uow_factory.get_uow(user_id=user_id) as uow:
        reference_id = (await uow.repositories.references.get(file_id=key)).id

    response = await client.post(GQL_API_PATH, json={
        "query": " mutation ( $ids: [ID!]! ) { referencesDelete( ids: $ids ) { status result errors { message } } } ",
        "variables": {"ids": [reference_id]}
    }, headers=with_auth(csrf_token=client.headers["X-CSRF-Token"], auth_token=login_token))
    assert_payload_success(get_verified_payload(response, "referencesDelete"))
    await bus.wait_until_idle()

    # the file is deleted, here and from the archive
    assert not Path(FILE_STORAGE_PATH, key).exists()
    record = await bus.archival_service.get(key)
    assert record.local_state == LocalState.EXPIRED
    assert record.archive_state == ArchiveState.DELETION_PENDING


async def run_retention(client):
    response = await client.post(
        "/retention/run?reason=test", headers={"Authorization": f"Bearer {RETENTION_AUTH_TOKEN}"}
    )
    assert response.status_code == 200, response.text


@pytest.mark.asyncio(loop_scope="session")
async def test_retention_removes_unused_file_references(
        reference_build_context,
        login_token_factory,
        client,
        uow_factory,
        bus
):
    """
    A file reference goes, with its file, once the retention job has found it unused, and it was not written,
    for UNUSED_REFERENCE_RETENTION_DAYS: counted from when it was unlinked, not from when it was created
    """
    user_id = reference_build_context['user_id']
    team_id = reference_build_context['team_id']
    login_token = login_token_factory(user_id)

    keys, reference_ids = {}, {}
    for name in ('old', 'cited_again', 'unlinked'):
        test_file_path = Path(FILE_STORAGE_PATH, f"test_retention_{name}.pdf")
        test_file_path.write_bytes(name.encode())
        with test_file_path.open("rb") as test_file:
            create_file_response = await post_to_create_file_reference(
                client,
                token=login_token,
                reference={'description': f'Test retention {name}', 'file': test_file},
                control_team_id=team_id
            )
        keys[name] = get_verified_payload(create_file_response, "referencesCreateFile").get('result')
        await wait_for_archival_record(bus.archival_service, keys[name])
        async with uow_factory.get_uow(user_id=user_id) as uow:
            reference_ids[name] = (await uow.repositories.references.get(file_id=keys[name])).id

    async def age(names, field: str):
        """Move the writes to the references, or the time they were found unused, back beyond the retention period"""
        ids = [reference_ids[name] for name in names]
        query = {
            'writes': " MATCH (reference: Reference)<-[write:CONTRIBUTED]-() WHERE reference.id IN $ids "
                      " SET write.time = datetime() - duration({days: $days + 1}) ",
            'unused': " MATCH (reference: Reference) WHERE reference.id IN $ids "
                      " SET reference.unused_since = datetime() - duration({days: $days + 1}) ",
        }[field]
        async with uow_factory.get_uow() as uow:
            await uow.tx.run(query, ids=ids, days=UNUSED_REFERENCE_RETENTION_DAYS)
            await uow.commit()

    async def remaining() -> set[int]:
        async with uow_factory.get_uow(user_id=user_id) as uow:
            return {reference.id async for reference in uow.repositories.references.get_all(
                reference_ids=list(reference_ids.values())
            )}

    async with uow_factory.get_uow(user_id=user_id, write_team=team_id) as uow:
        germplasm = await uow.germplasm.create_entry(
            GermplasmInput(name="Retention citer", references=[reference_ids['unlinked']])
        )
        germplasm_id = germplasm.id
        await uow.commit()
    # all were written long ago
    await age(reference_ids, 'writes')

    assert (await client.post("/retention/run?reason=test")).status_code == 401
    # the first run finds old and cited_again unused, and keeps them
    await run_retention(client)
    assert await remaining() == set(reference_ids.values())

    # old and cited_again have been unused for the period, but cited_again is cited again;
    # unlinked is unlinked long after it was written
    await age(['old', 'cited_again'], 'unused')
    async with uow_factory.get_uow(user_id=user_id, write_team=team_id) as uow:
        await uow.germplasm.create_entry(GermplasmInput(name="Retention citer 2", references=[reference_ids['cited_again']]))
        germplasm = await uow.germplasm.get_entry(germplasm_id)
        germplasm.references = []
        await uow.germplasm.update_entry(germplasm)
        await uow.commit()
    await run_retention(client)
    assert await remaining() == {reference_ids['cited_again'], reference_ids['unlinked']}

    # the old reference's file is deleted, here and from the archive; the others are kept
    assert not Path(FILE_STORAGE_PATH, keys['old']).exists()
    record = await bus.archival_service.get(keys['old'])
    assert record.local_state == LocalState.EXPIRED
    assert record.archive_state == ArchiveState.DELETION_PENDING
    for name in ('cited_again', 'unlinked'):
        assert Path(FILE_STORAGE_PATH, keys[name]).read_bytes() == name.encode()
        assert (await bus.archival_service.get(keys[name])).archive_state == ArchiveState.ARCHIVAL_PENDING

    # once unused for the period, the unlinked one goes too
    await age(['unlinked'], 'unused')
    await run_retention(client)
    assert await remaining() == {reference_ids['cited_again']}
    assert not Path(FILE_STORAGE_PATH, keys['unlinked']).exists()
