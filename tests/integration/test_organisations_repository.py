import pytest

from src.breedgraph.domain.model.organisations import TeamInput, Organisation
from src.breedgraph.adapters.repositories.organisations import Neo4jOrganisationRepository

from src.breedgraph.custom_exceptions import NoResultFoundError


async def create_team_input(user_input_generator, parent: int = None) -> TeamInput:
    user_input = user_input_generator.new_user_input()
    return TeamInput(
        name = user_input['team_name'],
        fullname = user_input['team_name'],
        parent = parent
    )

@pytest.mark.asyncio(scope="session")
async def test_create_extend_and_get_organisation(neo4j_tx, user_input_generator):
    team_input = await create_team_input(user_input_generator)
    organisations_repo = Neo4jOrganisationRepository(neo4j_tx)
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
    new_team_input = await create_team_input(user_input_generator, parent=organisation.root.id)
    organisation.add_team(new_team_input)

    # update db
    await organisations_repo.update_seen()

    # retrieve from db to ensure new team is now stored as child with ID
    retrieved_from_child_id = await organisations_repo.get(team_id=organisation.root.id)
    assert retrieved_from_child_id.root.id == organisation.root.id
    for team in retrieved_from_child_id.teams.values():
        if all([
            team.name == new_team_input.name,
            team.fullname == new_team_input.fullname,
            team.parent == organisation.root.id
        ]):
            assert team.id
            break
    else:
        raise NoResultFoundError

@pytest.mark.asyncio(scope="session")
async def test_edit_team_name(neo4j_tx, user_input_generator):
    organisations_repo = Neo4jOrganisationRepository(neo4j_tx)

    team_input = await create_team_input(user_input_generator)
    organisation = await organisations_repo.create(team_input)

    changed_team_input = await create_team_input(user_input_generator)
    organisation.root.name = changed_team_input.name
    organisation.root.fullname = changed_team_input.fullname

    await organisations_repo.update_seen()
    retrieved_from_root_id = await organisations_repo.get(team_id=organisation.root.id)
    assert retrieved_from_root_id.root == organisation.root

