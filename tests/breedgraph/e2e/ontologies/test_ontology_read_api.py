"""
The ontology queries under the read policy (docs/read-access.md, section 4), through GraphQL, on the read-policy
scenario: its types and variables are active, ontology_subject_draft is a draft, and the last commit, by the admin,
cites reference_registered as its licence and reference_legal_private as its copyright.

The ontology is not controlled by teams, so its reads are open, but anonymous users get the PUBLISHED and REFERENTIAL
views only: the EDITORIAL view, with drafts, needs an account. Commit history needs an account; a commit's person
is the committer's Person, its account shown only to its owner and admins of its teams, and its references are
placeholders where hidden. The lists of ontology editors, admins and role requests are for ontology admins only.
"""
import pytest

from breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus

from tests.breedgraph.e2e.utils import post_as, get_verified_payload
from tests.breedgraph.scenarios.read_policy_scenario import VIEWERS

REDACTED = 'REDACTED'
SUBJECTS = ('ontology_subject_field', 'ontology_subject_tree', 'ontology_subject_leaf', 'ontology_subject_rhizosphere')
ENTRY_FIELDS = "... on OntologyNodeInterface { id name phase view }"


async def payload_of(client, login_token_factory, read_policy, viewer: str, operation: str, text: str, variables=None):
    response = await post_as(client, login_token_factory, read_policy.user(viewer), text, variables)
    return get_verified_payload(response, operation)


async def result_of(client, login_token_factory, read_policy, viewer: str, operation: str, text: str, variables=None):
    payload = await payload_of(client, login_token_factory, read_policy, viewer, operation, text, variables)
    assert payload['status'] == GQLStatus.SUCCESS.name, payload['errors']
    assert payload['errors'] is None
    return payload['result']


def assert_refused(payload, error: str | None = None):
    assert payload['status'] != GQLStatus.SUCCESS.name
    assert payload['result'] is None
    if error is not None:
        assert [e['name'] for e in payload['errors']] == [error]


ENTRIES_BY_LABEL = (
    "query ($view: OntologyView) { ontologyEntries(labels: [SUBJECT], view: $view) { "
    f" status result {{ {ENTRY_FIELDS} }} errors {{ name message }} }} }}"
)


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_published_entries(client, login_token_factory, read_policy, viewer):
    result = await result_of(client, login_token_factory, read_policy, viewer, 'ontologyEntries', ENTRIES_BY_LABEL, {'view': 'PUBLISHED'})
    found = {int(entry['id']): entry for entry in result}
    assert {read_policy[name] for name in SUBJECTS} <= set(found)
    assert read_policy['ontology_subject_draft'] not in found
    assert all(entry['phase'] == 'ACTIVE' for entry in found.values())


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_editorial_entries_need_an_account(client, login_token_factory, read_policy, viewer):
    payload = await payload_of(client, login_token_factory, read_policy, viewer, 'ontologyEntries', ENTRIES_BY_LABEL, {'view': 'EDITORIAL'})
    if viewer == 'anonymous':
        assert_refused(payload, 'UnauthorisedOperationError')
        return
    assert payload['status'] == GQLStatus.SUCCESS.name, payload['errors']
    found = {int(entry['id']): entry for entry in payload['result']}
    assert {read_policy[name] for name in SUBJECTS} <= set(found)
    assert found[read_policy['ontology_subject_draft']]['phase'] == 'DRAFT'


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_referential_entries(client, login_token_factory, read_policy, viewer):
    """Entries as data refers to them, drafts included, for anyone"""
    result = await result_of(
        client, login_token_factory, read_policy, viewer, 'ontologyEntries',
        f"query ($ids: [ID!]) {{ ontologyEntries(ids: $ids, view: REFERENTIAL) {{ status result {{ {ENTRY_FIELDS} }} errors {{ name message }} }} }}",
        {'ids': [read_policy['ontology_subject_draft'], read_policy['ontology_subject_tree']]}
    )
    found = {int(entry['id']): entry for entry in result}
    assert set(found) == {read_policy['ontology_subject_draft'], read_policy['ontology_subject_tree']}
    assert found[read_policy['ontology_subject_draft']]['name'] == "Readpolicy draft subject"


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_whole_ontology(client, login_token_factory, read_policy, viewer):
    text = (
        "query ($view: OntologyView) { ontology(view: $view) { "
        f" status result {{ version {{ id }} entries {{ {ENTRY_FIELDS} }} }} errors {{ name message }} }} }}"
    )
    published = await result_of(client, login_token_factory, read_policy, viewer, 'ontology', text, {'view': 'PUBLISHED'})
    published_ids = {int(entry['id']) for entry in published['entries']}
    assert {read_policy[name] for name in SUBJECTS} <= published_ids
    assert read_policy['ontology_subject_draft'] not in published_ids

    editorial = await payload_of(client, login_token_factory, read_policy, viewer, 'ontology', text, {'view': 'EDITORIAL'})
    if viewer == 'anonymous':
        assert_refused(editorial, 'UnauthorisedOperationError')
    else:
        assert editorial['status'] == GQLStatus.SUCCESS.name, editorial['errors']
        assert read_policy['ontology_subject_draft'] in {int(entry['id']) for entry in editorial['result']['entries']}


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_version(client, login_token_factory, read_policy, viewer):
    version = await result_of(
        client, login_token_factory, read_policy, viewer, 'ontologyVersion',
        "query { ontologyVersion { status result { id } errors { name message } } }"
    )
    assert int(version['id']) == read_policy['ontology_commit_version']


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_commit_history(client, login_token_factory, read_policy, viewer):
    payload = await payload_of(
        client, login_token_factory, read_policy, viewer, 'ontologyCommitHistory',
        "query { ontologyCommitHistory(limit: 1) { status result { "
        "  version { id } comment user { id } person { id restricted } "
        "  licence { id description } copyright { id description } "
        "} errors { name message } } }"
    )
    if viewer == 'anonymous':
        assert_refused(payload)
        return
    assert payload['status'] == GQLStatus.SUCCESS.name, payload['errors']
    (commit,) = payload['result']
    assert int(commit['version']['id']) == read_policy['ontology_commit_version']
    assert commit['comment'] == "Readpolicy commit with references"
    # the account is shown to its owner only here (the admin is admin of no team the others are in)
    assert (commit['user'] is not None) == (viewer == 'admin'), f"{viewer}: commit user"
    # the committer's Person is public
    assert int(commit['person']['id']) == read_policy['person_admin']
    assert commit['person']['restricted'] is False
    for field, reference in (('licence', 'reference_registered'), ('copyright', 'reference_legal_private')):
        assert int(commit[field]['id']) == read_policy[reference]
        assert (commit[field]['description'] != REDACTED) == read_policy.readable(viewer, reference), f"{viewer}: {field}"


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
@pytest.mark.parametrize('operation', ('ontologyEditors', 'ontologyAdmins', 'ontologyRoleRequests'))
async def test_role_lists_are_for_ontology_admins(client, login_token_factory, read_policy, viewer, operation):
    payload = await payload_of(
        client, login_token_factory, read_policy, viewer, operation,
        f"query {{ {operation} {{ status result {{ id }} errors {{ name message }} }} }}"
    )
    # only the admin has the ontology admin role in the scenario
    if viewer == 'admin':
        assert payload['status'] == GQLStatus.SUCCESS.name, payload['errors']
    else:
        assert_refused(payload)
