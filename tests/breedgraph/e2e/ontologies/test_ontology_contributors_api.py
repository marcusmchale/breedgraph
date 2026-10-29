"""
The people listed as contributors to an ontology version (ontologyContributors), through GraphQL, on the read-policy
scenario, whose admin built its ontology and committed it (ontology_commit_version), and whose outsider has made none
of it. A person is listed only once they agree to it from their own account (peopleSetOntologyCredit), for anyone to
see, and only for the versions their work is in: the entries and relationships a version has, and the commit that made
it. A draft is in no version until a version is committed that publishes it, and a committer is credited with that
version alone; an author of an entry is no longer credited once a commit removes it, but still is for the versions
that had it.
"""
import pytest

from breedgraph.domain.model.accounts import OntologyRole
from breedgraph.domain.model.ontology import VersionChange
from breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus

from tests.breedgraph.e2e.utils import post_as, get_verified_payload
from tests.breedgraph.scenarios import OntologyBuilder

CONTRIBUTORS = "query ($version: ID) { ontologyContributors(versionId: $version) { status result { name institution orcid } errors { message } } }"
SET_CREDIT = "mutation ($listed: Boolean!) { peopleSetOntologyCredit(listed: $listed) { status errors { message } } }"
OWN_PERSON = "query { peopleMyPerson { result { ontologyCredit } } }"


async def _contributors(client, login_token_factory, version: int | None = None) -> list[str]:
    """The names listed, asked for anonymously"""
    payload = get_verified_payload(
        await post_as(client, login_token_factory, None, CONTRIBUTORS, {'version': None if version is None else str(version)}),
        'ontologyContributors'
    )
    assert payload['status'] == GQLStatus.SUCCESS.name, payload['errors']
    return [contributor['name'] for contributor in payload['result']]


async def _set_credit(client, login_token_factory, user_id: int, listed: bool) -> dict:
    return get_verified_payload(
        await post_as(client, login_token_factory, user_id, SET_CREDIT, {'listed': listed}), 'peopleSetOntologyCredit'
    )


async def _name(uow_factory, user_id: int) -> str:
    async with uow_factory.get_uow(user_id=user_id) as uow:
        return (await uow.repositories.people.get(user_id=user_id)).name


async def _commit(uow_factory, user_id: int, comment: str) -> int:
    async with uow_factory.get_uow(user_id=user_id) as uow:
        commit = await uow.ontology.commit_version(version_change=VersionChange.PATCH, comment=comment)
        await uow.commit()
    return commit.version.packed_version


async def _draft(uow_factory, user_id: int, name: str) -> int:
    async with uow_factory.get_uow(user_id=user_id) as uow:
        entry = await uow.ontology.create_entry(OntologyBuilder.subject_input(name=name))
        await uow.commit()
    return entry.id


@pytest.mark.asyncio(loop_scope="session")
async def test_listed_by_agreement_and_only_for_the_versions_their_work_is_in(
        client, login_token_factory, read_policy, uow_factory
):
    admin, outsider = read_policy.user('admin'), read_policy.user('outsider')
    committed = read_policy['ontology_commit_version']
    admin_name, outsider_name = await _name(uow_factory, admin), await _name(uow_factory, outsider)
    both = sorted([admin_name, outsider_name], key=str.lower)

    # no one has agreed yet, though everyone who contributes is credited together
    assert await _contributors(client, login_token_factory) == []

    payload = await _set_credit(client, login_token_factory, admin, True)
    assert payload['status'] == GQLStatus.SUCCESS.name, payload['errors']
    assert await _contributors(client, login_token_factory) == [admin_name]
    person = get_verified_payload(await post_as(client, login_token_factory, admin, OWN_PERSON), 'peopleMyPerson')['result']
    assert person['ontologyCredit'] is True

    # the outsider agrees and, as an editor, commits a version: they are credited with that version alone
    assert (await _set_credit(client, login_token_factory, outsider, True))['status'] == GQLStatus.SUCCESS.name
    async with uow_factory.get_uow() as uow:
        account = await uow.repositories.accounts.get(user_id=outsider)
        account.user.ontology_role = OntologyRole.EDITOR
        await uow.commit()
    outsiders = await _commit(uow_factory, outsider, "Committed by the outsider")
    assert await _contributors(client, login_token_factory, outsiders) == both
    assert await _contributors(client, login_token_factory, committed) == [admin_name]
    after = await _commit(uow_factory, admin, "Committed by the admin")
    assert await _contributors(client, login_token_factory, after) == [admin_name]

    # a draft is in no version until the next commit publishes it
    drafted = await _draft(uow_factory, outsider, "Contributed subject")
    assert await _contributors(client, login_token_factory) == [admin_name]
    published = await _commit(uow_factory, admin, "Publishes the outsider's subject")
    assert await _contributors(client, login_token_factory, published) == both
    assert await _contributors(client, login_token_factory, after) == [admin_name]

    # deprecated, the subject is still in the version that deprecates it; once a commit removes it, its author is no
    # longer credited, but still is for the versions that had it
    async with uow_factory.get_uow(user_id=admin) as uow:
        await uow.ontology.deprecate_entries([drafted])
        await uow.commit()
    removed = await _commit(uow_factory, admin, "Removes the outsider's subject")
    assert await _contributors(client, login_token_factory, removed) == [admin_name]
    assert await _contributors(client, login_token_factory, published) == both

    # withdrawing takes them off every version
    assert (await _set_credit(client, login_token_factory, outsider, False))['status'] == GQLStatus.SUCCESS.name
    assert await _contributors(client, login_token_factory, published) == [admin_name]
    assert await _contributors(client, login_token_factory, outsiders) == [admin_name]


@pytest.mark.asyncio(loop_scope="session")
async def test_only_a_user_with_a_person_can_be_listed(client, login_token_factory, read_policy):
    # the writer's account is linked to no Person, and an anonymous request has no account
    payload = await _set_credit(client, login_token_factory, read_policy.user('writer'), True)
    assert payload['status'] != GQLStatus.SUCCESS.name
    assert 'not linked to a Person' in payload['errors'][0]['message']
    payload = await _set_credit(client, login_token_factory, None, True)
    assert payload['status'] != GQLStatus.SUCCESS.name
