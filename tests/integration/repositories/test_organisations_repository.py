import pytest
import pytest_asyncio

from src.breedgraph.custom_exceptions import IllegalOperationError
from src.breedgraph.domain.model.organisations import TeamInput, TeamStored, Access, Authorisation, Affiliation, Organisation
from src.breedgraph.adapters.neo4j.repositories import Neo4jOrganisationsRepository

from src.breedgraph.custom_exceptions import NoResultFoundError

async def create_team_input(user_input_generator) -> TeamInput:
    user_input = user_input_generator.new_user_input()
    return TeamInput(
        name = user_input['team_name'],
        fullname = user_input['team_name']
    )

@pytest.mark.usefixtures("session_database")
@pytest.mark.asyncio(scope="session")
async def test_create_extend_and_get_organisation(uncommitted_neo4j_tx, first_unstored_account, user_input_generator):
    team_input = await create_team_input(user_input_generator)

    organisations_repo = Neo4jOrganisationsRepository(tx=uncommitted_neo4j_tx, user_id=first_unstored_account.user.id)
    organisation = await organisations_repo.create(team_input)

    # test that retrieve by id works
    retrieved_from_root_id = await organisations_repo.get(team_id=organisation.root.id)
    assert retrieved_from_root_id.root.name == team_input.name
    # test that retrieve all includes the submitted entry
    async for org in organisations_repo.get_all():
        if org.root.name == team_input.name:
            break
    else:
        raise NoResultFoundError

    # Add a child
    new_team_input = await create_team_input(user_input_generator)
    organisation.add_team(new_team_input, parent_id=organisation.root.id)
    # update db
    await organisations_repo.update_seen()
    # get child id
    child_id = organisation.get_children(organisation.root.id)[0]
    # retrieve from db by child ID
    retrieved_from_child_id = await organisations_repo.get(team_id=child_id)
    assert retrieved_from_child_id.root.id == organisation.root.id
    for team in retrieved_from_child_id.teams:
        if all([
            team.name == new_team_input.name,
            team.fullname == new_team_input.fullname
        ]):
            assert team.id
            break
    else:
        raise NoResultFoundError

@pytest.mark.asyncio(scope='session')
async def test_request_remove_affiliation(uncommitted_neo4j_tx, user_input_generator, first_unstored_account, second_unstored_account):
    organisations_repo = Neo4jOrganisationsRepository(tx=uncommitted_neo4j_tx, user_id=first_unstored_account.user.id)
    team_input = await create_team_input(user_input_generator)
    organisation = await organisations_repo.create(team_input)
    assert first_unstored_account.user.id in organisation.get_affiliates(organisation.root.id)
    organisation.request_affiliation(
        agent_id=second_unstored_account.root.id,
        team_id=organisation.root.id,
        access=Access.READ,
        user_id=second_unstored_account.root.id,
        heritable=True
    )
    await organisations_repo.update_seen()
    retrieved = await organisations_repo.get(team_id=organisation.root.id)
    assert second_unstored_account.user.id in retrieved.get_affiliates(organisation.root.id, access=Access.READ, authorisation=Authorisation.REQUESTED)

    # now remove it (as it is just requested should be completely gone
    retrieved.remove_affiliation(
        agent_id=second_unstored_account.root.id,
        team_id=organisation.root.id,
        access=Access.READ,
        user_id=second_unstored_account.root.id
    )
    await organisations_repo.update_seen()

    retrieved_again = await organisations_repo.get(team_id=organisation.root.id)
    assert second_unstored_account.user.id not in retrieved_again.get_affiliates(organisation.root.id, access=Access.READ, authorisation=Authorisation.REQUESTED)

@pytest.mark.asyncio(scope='session')
async def test_request_authorise_revoke_affiliation(uncommitted_neo4j_tx, user_input_generator, first_unstored_account, second_unstored_account):
    organisations_repo = Neo4jOrganisationsRepository(uncommitted_neo4j_tx, user_id=first_unstored_account.user.id)
    team_input = await create_team_input(user_input_generator)
    organisation = await organisations_repo.create(team_input)
    assert first_unstored_account.user.id in organisation.get_affiliates(organisation.root.id)
    organisation.request_affiliation(
        agent_id=second_unstored_account.root.id,
        team_id=organisation.root.id,
        access=Access.READ,
        user_id=second_unstored_account.root.id,
        heritable=True
    )
    organisation.authorise_affiliation(
        agent_id=first_unstored_account.root.id,
        team_id=organisation.root.id,
        access=Access.READ,
        user_id=second_unstored_account.root.id,
        heritable=True
    )

    await organisations_repo.update_seen()
    retrieved = await organisations_repo.get(team_id=organisation.root.id)
    assert second_unstored_account.user.id in retrieved.get_affiliates(organisation.root.id, access=Access.READ, authorisation=Authorisation.AUTHORISED)

    retrieved.revoke_affiliation(
        agent_id=first_unstored_account.root.id,
        team_id=organisation.root.id,
        access=Access.READ,
        user_id=second_unstored_account.root.id
    )
    await organisations_repo.update_seen()
    retrieved_again = await organisations_repo.get(team_id=organisation.root.id)
    assert second_unstored_account.user.id not in retrieved_again.get_affiliates(organisation.root.id, access=Access.READ)

@pytest.mark.asyncio(scope="session")
async def test_remove_team(uncommitted_neo4j_tx, user_input_generator, first_unstored_account):
    team_input = await create_team_input(user_input_generator)
    organisations_repo = Neo4jOrganisationsRepository(uncommitted_neo4j_tx, user_id=first_unstored_account.user.id)
    organisation = await organisations_repo.create(team_input)
    new_team_input = await create_team_input(user_input_generator)
    organisation.add_team(new_team_input, parent_id=organisation.root.id)
    await organisations_repo.update_seen()
    with pytest.raises(IllegalOperationError):
        organisation.remove_team(organisation.root.id)

    child_id = organisation.get_children(organisation.root.id)[0]
    organisation.remove_team(child_id)
    assert organisation.size == 1
    await organisations_repo.update_seen()
    retrieved = await organisations_repo.get(team_id=organisation.root.id)
    assert retrieved.size == 1

@pytest.mark.asyncio(scope="session")
async def test_edit_team_name(uncommitted_neo4j_tx, user_input_generator, first_unstored_account):
    organisations_repo = Neo4jOrganisationsRepository(uncommitted_neo4j_tx, user_id=first_unstored_account.user.id)
    team_input = await create_team_input(user_input_generator)
    organisation = await organisations_repo.create(team_input)

    changed_team_input = await create_team_input(user_input_generator)
    organisation.root.name = changed_team_input.name
    organisation.root.fullname = changed_team_input.fullname

    await organisations_repo.update_seen()
    retrieved_from_root_id = await organisations_repo.get(team_id=organisation.root.id)
    assert retrieved_from_root_id.root.id == organisation.root.id
    assert retrieved_from_root_id.root.name == changed_team_input.name
    assert retrieved_from_root_id.root.fullname == changed_team_input.fullname

@pytest.mark.asyncio(scope="session")
async def test_move_team_without_cycles(uncommitted_neo4j_tx, user_input_generator, first_unstored_account):
    organisations_repo = Neo4jOrganisationsRepository(uncommitted_neo4j_tx, user_id=first_unstored_account.user.id)
    team_input = await create_team_input(user_input_generator)
    organisation = await organisations_repo.create(team_input)
    second_team_input = await create_team_input(user_input_generator)
    organisation.add_team(second_team_input, parent_id=organisation.root.id)
    third_team_input = await create_team_input(user_input_generator)
    organisation.add_team(third_team_input, parent_id=organisation.root.id)
    await organisations_repo.update_seen()

    second_team = organisation.get_team(second_team_input.name)
    third_team = organisation.get_team(third_team_input.name)
    organisation.change_source(third_team.id, second_team.id)
    await organisations_repo.update_seen()

    retrieved_from_root_id = await organisations_repo.get(team_id=organisation.root.id)
    assert second_team.id in retrieved_from_root_id._graph.successors(organisation.root.id)
    assert third_team.id in retrieved_from_root_id._graph.successors(second_team.id)

@pytest.mark.asyncio(scope="session")
async def test_split_and_merge_organisation(uncommitted_neo4j_tx, user_input_generator, first_unstored_account):
    organisations_repo = Neo4jOrganisationsRepository(uncommitted_neo4j_tx, first_unstored_account.user.id)
    team_input = await create_team_input(user_input_generator)
    organisation = await organisations_repo.create(team_input)
    second_team_input = await create_team_input(user_input_generator)
    organisation.add_team(second_team_input, parent_id =organisation.root.id)
    third_team_input = await create_team_input(user_input_generator)
    organisation.add_team(third_team_input, parent_id=organisation.root.id)
    await organisations_repo.update_seen()

    third_team = organisation.get_team(third_team_input.name)
    await organisations_repo.split(third_team.id)
    await organisations_repo.update_seen()

    old_org = await organisations_repo.get(team_id=organisation.root.id)
    new_org = await organisations_repo.get(team_id=third_team.id)

    assert old_org.size == 2
    assert new_org.size == 1

    old_org.add_team(third_team, parent_id=old_org.root.id)
    await organisations_repo.update_seen()

    org = await organisations_repo.get(team_id = organisation.root.id)
    assert org.size == 3
