"""
The standard licences through GraphQL (docs/licences.md §6): referencesStandardLicences lists them, CC BY 4.0 first,
to anyone, and each one's controller says it is fixed, with a public release and read access alone, for an
administrator of every team too (docs/read-access.md, rule 11).
"""
import pytest

from breedgraph.service_layer.application.licence_seed import STANDARD_LICENCES

from tests.breedgraph.e2e.utils import post_as, get_verified_payload, assert_payload_success
from tests.breedgraph.scenarios.account_builder import AccountBuilder

STANDARD_LICENCES_QUERY = """
query { referencesStandardLicences { status result { __typename id description ... on LegalReference { text contentHash } } errors { message } } }
"""
CONTROLLERS_QUERY = """
query($ids: [ID!]!) { controlsControllers(entityLabel: REFERENCE, entityIds: $ids) {
  status result { fixed release access controls { release } } errors { message }
} }
"""


@pytest.mark.asyncio(loop_scope="session")
async def test_anyone_reads_the_standard_licences_in_order(client, login_token_factory):
    payload = get_verified_payload(
        await post_as(client, login_token_factory, None, STANDARD_LICENCES_QUERY), 'referencesStandardLicences'
    )
    assert_payload_success(payload)
    licences = payload['result']
    assert [licence['description'] for licence in licences] == [licence.description for licence in STANDARD_LICENCES]
    for licence, standard in zip(licences, STANDARD_LICENCES):
        assert licence['__typename'] == 'LegalReference'
        assert licence['text'] == standard.text
        assert licence['contentHash'] == standard.reference_input().content_hash


@pytest.mark.asyncio(loop_scope="session")
async def test_the_standard_licences_are_fixed(client, login_token_factory, uow_factory):
    admin = await AccountBuilder(uow_factory).account_with_affiliations()
    licences = get_verified_payload(
        await post_as(client, login_token_factory, admin['user_id'], STANDARD_LICENCES_QUERY), 'referencesStandardLicences'
    )['result']
    payload = get_verified_payload(
        await post_as(client, login_token_factory, admin['user_id'], CONTROLLERS_QUERY, {'ids': [l['id'] for l in licences]}),
        'controlsControllers'
    )
    assert_payload_success(payload)
    assert payload['result'] == [
        {'fixed': True, 'release': 'PUBLIC', 'access': ['READ'], 'controls': []} for _ in licences
    ]
