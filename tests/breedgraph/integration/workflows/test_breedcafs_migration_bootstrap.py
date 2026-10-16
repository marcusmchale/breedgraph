import pytest
import pytest_asyncio

from breedgraph.domain.model.controls import Access
from breedgraph.domain.model.team_trees import TeamTree

from breedcafs_migration import bootstrap
from breedcafs_migration.bootstrap import setup_breedcafs_migration_account, MigrationSettingsError

from tests.breedgraph.scenarios.account_builder import AccountBuilder
from tests.breedgraph.scenarios.team_tree_builder import TeamTreeBuilder

TERMS_VERSION = "test"


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def university_context(isolated_state, uow_factory) -> dict[str, int]:
    """An admin with heritable admin access to the root team of a team tree"""
    admin_id = await AccountBuilder(uow_factory=uow_factory).account()
    team_tree_builder = TeamTreeBuilder(uow_factory=uow_factory)
    root_id = await team_tree_builder.team_tree(user_id=admin_id)
    await team_tree_builder.authorise_access(user_id=admin_id, team_id=root_id, access=Access.ADMIN, heritable=True)
    return {'admin_id': admin_id, 'root_id': root_id}


@pytest.fixture
def migration_config(monkeypatch, university_context):
    monkeypatch.setattr(bootstrap, 'BREEDCAFS_ADMIN_USER_ID', str(university_context['admin_id']))
    monkeypatch.setattr(bootstrap, 'BREEDCAFS_PARENT_TEAM_ID', str(university_context['root_id']))


async def declare_legal_entity(uow_factory, admin_id: int, root_id: int):
    async with uow_factory.get_uow(user_id=admin_id) as uow:
        team_tree = await uow.repositories.team_trees.get(team_id=root_id)
        team_tree.declare_legal_entity(
            agent_id=admin_id,
            team_id=root_id,
            legal_name="University",
            privacy_contact="dataprotection@example.org",
            terms_version=TERMS_VERSION,
            current_terms_version=TERMS_VERSION
        )
        await uow.commit()


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize("admin_id, parent_id, message", [
    (None, "1", "BREEDCAFS_ADMIN_USER_ID is not set"),
    ("1", " ", "BREEDCAFS_PARENT_TEAM_ID is not set"),
    ("admin", "1", "BREEDCAFS_ADMIN_USER_ID must be an id"),
])
async def test_bootstrap_requires_settings(uow_factory, monkeypatch, admin_id, parent_id, message):
    monkeypatch.setattr(bootstrap, 'BREEDCAFS_ADMIN_USER_ID', admin_id)
    monkeypatch.setattr(bootstrap, 'BREEDCAFS_PARENT_TEAM_ID', parent_id)
    with pytest.raises(MigrationSettingsError, match=message):
        await setup_breedcafs_migration_account(uow_factory)


@pytest.mark.asyncio(loop_scope="session")
async def test_bootstrap_requires_legal_entity(uow_factory, migration_config):
    with pytest.raises(MigrationSettingsError, match="legal entity"):
        await setup_breedcafs_migration_account(uow_factory)


@pytest.mark.asyncio(loop_scope="session")
async def test_bootstrap_creates_migration_team_and_user(uow_factory, university_context, migration_config):
    admin_id = university_context['admin_id']
    root_id = university_context['root_id']
    await declare_legal_entity(uow_factory, admin_id, root_id)

    context = await setup_breedcafs_migration_account(uow_factory)

    async with uow_factory.get_uow(user_id=admin_id) as uow:
        team_tree: TeamTree = await uow.repositories.team_trees.get(team_id=context.team_id)
        assert team_tree.get_root_id() == root_id
        assert team_tree.get_parent_id(context.team_id) == root_id
        for access in [Access.READ, Access.WRITE, Access.CURATE]:
            assert context.user_id in team_tree.get_affiliates(context.team_id, access, inheritance=False)
        assert context.user_id not in team_tree.get_affiliates(context.team_id, Access.ADMIN)
        assert context.user_id not in team_tree.get_affiliates(root_id)

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
        team_tree: TeamTree = await uow.repositories.team_trees.get(team_id=university_context['root_id'])
        assert len(team_tree.get_children(university_context['root_id'])) == 1
