"""
An upload asked for while as many files as may be saved at once are being saved (MAX_CONCURRENT_UPLOADS) is refused
with why, before anything is stored, rather than accepted and then failing in the background
"""
import uuid

import pytest

from breedgraph.config import MAX_CONCURRENT_UPLOADS

from tests.breedgraph.e2e.references.post_methods import post_with_file
from tests.breedgraph.e2e.utils import get_verified_payload

CREATE_FILE = """
    mutation ($reference: FileReferenceInput!, $controlTeamId: ID!) {
        referencesCreateFile(reference: $reference, controlTeamId: $controlTeamId) {
            status result errors { name message }
        }
    }
"""


@pytest.mark.asyncio(loop_scope="session")
async def test_an_upload_is_refused_while_every_place_is_taken(client, bus, reference_build_context, login_token_factory, uow_factory):
    context = reference_build_context
    description = f'Refused upload {uuid.uuid4().hex}'
    semaphore = bus.file_management.upload_semaphore
    for _ in range(MAX_CONCURRENT_UPLOADS):
        await semaphore.acquire()
    try:
        response = await post_with_file(
            client, login_token_factory(context['user_id']), CREATE_FILE,
            {"reference": {"description": description, "file": None}, "controlTeamId": context['team_id']},
            "reference.file", 'heights.csv', b'unit,height\n', 'text/csv'
        )
    finally:
        for _ in range(MAX_CONCURRENT_UPLOADS):
            semaphore.release()

    payload = get_verified_payload(response, "referencesCreateFile")
    assert payload['status'] == 'ERROR' and payload['result'] is None
    assert [error['name'] for error in payload['errors']] == ['TooManyUploadsError']
    assert 'try again' in payload['errors'][0]['message']
    # no reference was made for it
    async with uow_factory.get_uow() as uow:
        result = await uow.tx.run("MATCH (reference:Reference {description: $description}) RETURN count(reference) AS count", description=description)
        assert (await result.single())['count'] == 0
