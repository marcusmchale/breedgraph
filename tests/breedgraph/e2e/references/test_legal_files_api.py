"""
Legal references given as files (docs/licences.md): a .txt, .md or .pdf whose text is read on upload, with the file's
SHA-256 as the content hash, and the file saved and served as other files are
"""
import asyncio
import hashlib
from pathlib import Path

import pytest

from breedgraph.config import FILE_STORAGE_PATH
from tests.breedgraph.e2e.references.post_methods import (
    post_to_create_legal_file_reference,
    post_to_update_legal_file_reference,
    post_to_file_submission,
    post_to_file_download
)
from tests.breedgraph.e2e.utils import get_verified_payload, assert_payload_success, post_as
from tests.breedgraph.utilities.documents import pdf_with_text

LEGAL_FIELDS = """
    query ($ids: [ID!]) { references(ids: $ids) { status result {
        id description
        ... on LegalReference { text textFormat contentHash filename contentType fileId }
    } errors { message } } }
"""

UPDATE_LEGAL = """
    mutation ($reference: LegalReferenceUpdate!) {
        referencesUpdateLegal(reference: $reference) { status result errors { message } }
    }
"""


async def saved(client, token: str, key: str) -> int:
    """The id of the reference whose file is saved under key, once it is"""
    for _ in range(50):
        result = get_verified_payload(await post_to_file_submission(client, token=token, file_id=key), "referencesFileSubmission")['result']
        if result['status'] == 'COMPLETED':
            return int(result['referenceId'])
        assert result['status'] != 'FAILED', result['errors']
        await asyncio.sleep(0.1)
    raise AssertionError(f"File {key} was not saved")


async def legal_reference(client, login_token_factory, user_id: int, reference_id: int) -> dict:
    payload = get_verified_payload(await post_as(client, login_token_factory, user_id, LEGAL_FIELDS, {'ids': [reference_id]}), "references")
    assert_payload_success(payload)
    return payload['result'][0]


async def with_file(client, login_token_factory, user_id: int, reference_id: int, key: str) -> dict:
    """
    The reference once it points to the file saved under key: the submission is complete before UploadCompleted, an
    event, links the file
    """
    for _ in range(50):
        reference = await legal_reference(client, login_token_factory, user_id, reference_id)
        if reference['fileId'] == key:
            return reference
        await asyncio.sleep(0.1)
    raise AssertionError(f"Reference {reference_id} was not linked to file {key}")


async def file_removed(file_id: str) -> bool:
    """Whether the stored file is gone; a replaced file is deleted once the reference no longer points to it"""
    for _ in range(50):
        if not Path(FILE_STORAGE_PATH, file_id).exists():
            return True
        await asyncio.sleep(0.1)
    return False


@pytest.mark.asyncio(loop_scope="session")
async def test_a_licence_given_as_a_markdown_file(reference_build_context, login_token_factory, client):
    user_id, team_id = reference_build_context['user_id'], reference_build_context['team_id']
    token = login_token_factory(user_id)
    content = b'# Licence\n\nUse the data **with credit**.\n'

    # the client's content type is not trusted: the extension decides
    payload = get_verified_payload(
        await post_to_create_legal_file_reference(client, token, team_id, 'licence.md', content, 'application/octet-stream'),
        "referencesCreateLegalFile"
    )
    assert_payload_success(payload)
    key = payload['result']
    reference_id = await saved(client, token, key)

    reference = await with_file(client, login_token_factory, user_id, reference_id, key)
    assert reference == {
        'id': str(reference_id),
        'description': 'licence.md',
        'text': '# Licence\n\nUse the data **with credit**.',
        'textFormat': 'MARKDOWN',
        'contentHash': hashlib.sha256(content).hexdigest(),
        'filename': 'licence.md',
        'contentType': 'text/markdown; charset=utf-8',
        'fileId': key
    }

    download = get_verified_payload(await post_to_file_download(client, token=token, file_id=key), "referencesFileDownload")
    assert_payload_success(download)
    assert (await client.get(download['result']['url'])).content == content


@pytest.mark.asyncio(loop_scope="session")
async def test_a_wrong_file_is_refused_at_once(reference_build_context, login_token_factory, client):
    token = login_token_factory(reference_build_context['user_id'])
    for filename, content, message in (
        ('licence.docx', b'PK\x03\x04', '.txt, .md or .pdf'),
        ('licence.pdf', pdf_with_text(''), 'no text to read'),
    ):
        payload = get_verified_payload(
            await post_to_create_legal_file_reference(client, token, reference_build_context['team_id'], filename, content, 'application/pdf'),
            "referencesCreateLegalFile"
        )
        assert payload['status'] == 'ERROR'
        assert message in payload['errors'][0]['message']


@pytest.mark.asyncio(loop_scope="session")
async def test_new_text_from_a_file_replaces_the_old_file(reference_build_context, login_token_factory, client):
    user_id, team_id = reference_build_context['user_id'], reference_build_context['team_id']
    token = login_token_factory(user_id)
    created = get_verified_payload(
        await post_to_create_legal_file_reference(client, token, team_id, 'terms.txt', b'Use with credit.', 'text/plain', description='Terms'),
        "referencesCreateLegalFile"
    )
    old_key = created['result']
    reference_id = await saved(client, token, old_key)
    await with_file(client, login_token_factory, user_id, reference_id, old_key)

    content = pdf_with_text('Terms, second version', 'Use with credit, and say what you changed.')
    updated = get_verified_payload(
        await post_to_update_legal_file_reference(client, token, reference_id, 'terms-2.pdf', content, 'application/pdf'),
        "referencesUpdateLegalFile"
    )
    assert_payload_success(updated)
    new_key = updated['result']
    assert await saved(client, token, new_key) == reference_id

    reference = await with_file(client, login_token_factory, user_id, reference_id, new_key)
    assert reference['description'] == 'Terms'
    assert 'Terms, second version' in reference['text'] and 'say what you changed' in reference['text']
    assert reference['textFormat'] == 'PLAIN'
    assert reference['contentHash'] == hashlib.sha256(content).hexdigest()
    assert (reference['filename'], reference['contentType'], reference['fileId']) == ('terms-2.pdf', 'application/pdf', new_key)
    assert await file_removed(old_key)


@pytest.mark.asyncio(loop_scope="session")
async def test_typed_text_replaces_a_file_and_the_same_text_keeps_it(reference_build_context, login_token_factory, client):
    user_id, team_id = reference_build_context['user_id'], reference_build_context['team_id']
    token = login_token_factory(user_id)
    content = b'Use with credit.'
    key = get_verified_payload(
        await post_to_create_legal_file_reference(client, token, team_id, 'terms.txt', content, 'text/plain'),
        "referencesCreateLegalFile"
    )['result']
    reference_id = await saved(client, token, key)
    await with_file(client, login_token_factory, user_id, reference_id, key)

    async def update(**fields):
        payload = get_verified_payload(
            await post_as(client, login_token_factory, user_id, UPDATE_LEGAL, {'reference': {'id': reference_id, **fields}}),
            "referencesUpdateLegal"
        )
        assert_payload_success(payload)
        return await legal_reference(client, login_token_factory, user_id, reference_id)

    # a new description, or the same text again, changes neither the file nor what an acceptance names
    for fields in ({'description': 'Terms of use'}, {'text': 'Use with credit.'}):
        reference = await update(**fields)
        assert (reference['fileId'], reference['contentHash']) == (key, hashlib.sha256(content).hexdigest())

    reference = await update(text='Use with credit, in **bold**.', textFormat='MARKDOWN')
    assert reference['text'] == 'Use with credit, in **bold**.'
    assert reference['textFormat'] == 'MARKDOWN'
    assert reference['contentHash'] == hashlib.sha256('Use with credit, in **bold**.'.encode()).hexdigest()
    assert (reference['filename'], reference['contentType'], reference['fileId']) == (None, None, None)
    assert await file_removed(key)
