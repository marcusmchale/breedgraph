import pytest
import pytest_asyncio

from breedgraph.domain.model.controls import Access
from breedgraph.domain.model.organisations import Organisation

from breedcafs_migration import bootstrap
from breedcafs_migration.bootstrap import setup_breedcafs_migration_account

from tests.breedgraph.scenarios.account_builder import AccountBuilder
from tests.breedgraph.scenarios.organisation_builder import OrganisationBuilder

TERMS_VERSION = "test"


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def university_context(isolated_state, uow_factory) -> dict[str, int]:
    """An admin with heritable admin access to the root team of an organisation"""
    admin_id = await AccountBuilder(uow_factory=uow_factory).account()
    organisation_builder = OrganisationBuilder(uow_factory=uow_factory)
    root_id = await organisation_builder.organisation(user_id=admin_id)
    await organisation_builder.authorise_access(user_id=admin_id, team_id=root_id, access=Access.ADMIN, heritable=True)
    return {'admin_id': admin_id, 'root_id': root_id}


@pytest.fixture
def migration_config(monkeypatch, university_context):
    monkeypatch.setattr(bootstrap, 'BREEDCAFS_ADMIN_USER_ID', str(university_context['admin_id']))
    monkeypatch.setattr(bootstrap, 'BREEDCAFS_PARENT_TEAM_ID', str(university_context['root_id']))


async def declare_legal_entity(uow_factory, admin_id: int, root_id: int):
    async with uow_factory.get_uow(user_id=admin_id) as uow:
        organisation = await uow.repositories.organisations.get(team_id=root_id)
        organisation.declare_legal_entity(
            agent_id=admin_id,
            team_id=root_id,
            legal_name="University",
            privacy_contact="dataprotection@example.org",
            terms_version=TERMS_VERSION,
            current_terms_version=TERMS_VERSION
        )
        await uow.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_bootstrap_requires_legal_entity(uow_factory, migration_config):
    with pytest.raises(ValueError, match="legal entity"):
        await setup_breedcafs_migration_account(uow_factory)


@pytest.mark.asyncio(loop_scope="session")
async def test_bootstrap_creates_migration_team_and_user(uow_factory, university_context, migration_config):
    admin_id = university_context['admin_id']
    root_id = university_context['root_id']
    await declare_legal_entity(uow_factory, admin_id, root_id)

    context = await setup_breedcafs_migration_account(uow_factory)

    async with uow_factory.get_uow(user_id=admin_id) as uow:
        organisation: Organisation = await uow.repositories.organisations.get(team_id=context.team_id)
        assert organisation.get_root_id() == root_id
        assert organisation.get_parent_id(context.team_id) == root_id
        for access in [Access.READ, Access.WRITE, Access.CURATE]:
            assert context.user_id in organisation.get_affiliates(context.team_id, access, inheritance=False)
        assert context.user_id not in organisation.get_affiliates(context.team_id, Access.ADMIN)
        assert context.user_id not in organisation.get_affiliates(root_id)

        account = await uow.repositories.accounts.get(user_id=context.user_id)
        assert account.user.password_hash == ''
        assert account.user.email == ''
        assert account.user.default_write_team == context.team_id


@pytest.mark.asyncio(loop_scope="session")
async def test_bootstrap_reuses_existing_migration_team_and_user(uow_factory, university_context, migration_config):
    first = await setup_breedcafs_migration_account(uow_factory)
    second = await setup_breedcafs_migration_account(uow_factory)
    assert first == second

    async with uow_factory.get_uow(user_id=university_context['admin_id']) as uow:
        organisation: Organisation = await uow.repositories.organisations.get(team_id=university_context['root_id'])
        assert len(organisation.get_children(university_context['root_id'])) == 1
