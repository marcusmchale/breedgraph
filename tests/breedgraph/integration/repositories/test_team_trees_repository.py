import pytest

from breedgraph.domain.model.team_trees import Authorisation
from breedgraph.domain.model import Access
from breedgraph.custom_exceptions import NoResultFoundError

from tests.breedgraph.scenarios.team_tree_builder import TeamTreeBuilder

@pytest.mark.asyncio(loop_scope="session")
async def test_create_get_extend(
        uow_factory,
        team_tree_build_context
):
    team_input_1 = TeamTreeBuilder.team_input()
    team_input_2 = TeamTreeBuilder.team_input()
    user_id = team_tree_build_context['user_id']
    async with uow_factory.get_uow(user_id=user_id) as uow:
        team_tree = await uow.repositories.team_trees.create(team_input_1)
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        team_tree = await uow.repositories.team_trees.get(team_id=team_tree.root.id)
        assert team_tree.root.name == team_input_1.name

        async for team_tree in uow.repositories.team_trees.get_all():
            if team_tree.root.name == team_input_1.name:
                break
        else:
            raise NoResultFoundError("TeamTree not retrieved by get all")

        # Add a child
        team_tree.add_team(team_input_2, parent_id=team_tree.root.id)
        await uow.repositories.team_trees.update_seen()

        # get child id
        child_id = team_tree.get_children(team_tree.root.id)[0]
        # retrieve from db by child ID
        retrieved_from_child_id = await uow.repositories.team_trees.get(team_id=child_id)
        assert retrieved_from_child_id.root.id == team_tree.root.id
        for team in retrieved_from_child_id.teams:
            if all([
                team.name == team_input_2.name,
                team.fullname == team_input_2.fullname
            ]):
                assert team.id
                break
        else:
            raise NoResultFoundError

@pytest.mark.asyncio(loop_scope='session')
async def test_request_remove_affiliation(
        uow_factory,
        team_tree_build_context
):
    user_id_1 = team_tree_build_context['user_id_1']
    user_id_2 = team_tree_build_context['user_id_2']
    team_input = TeamTreeBuilder.team_input()
    async with uow_factory.get_uow(user_id=user_id_1) as uow:
        team_tree = await uow.repositories.team_trees.create(team_input)
        assert user_id_1 in team_tree.get_affiliates(team_tree.root.id)
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id_2) as uow:
        team_tree = await uow.repositories.team_trees.get(team_id=team_tree.root.id)
        team_tree.request_affiliation(
            agent_id=user_id_2,
            team_id=team_tree.root.id,
            access=Access.READ,
            user_id=user_id_2,
            heritable=True
        )
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id_1) as uow:
        team_tree = await uow.repositories.team_trees.get(team_id=team_tree.root.id)
        assert user_id_2 in team_tree.get_affiliates(
            team_tree.root.id,
            access=Access.READ,
            authorisation=Authorisation.REQUESTED
        )
        team_tree.remove_affiliation(
            agent_id=user_id_1,
            team_id=team_tree.root.id,
            access=Access.READ,
            user_id=user_id_2
        )
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id_1) as uow:
        team_tree = await uow.repositories.team_trees.get(team_id=team_tree.root.id)
        assert user_id_2 not in team_tree.get_affiliates(team_tree.root.id, access=Access.READ, authorisation=Authorisation.REQUESTED)

@pytest.mark.asyncio(loop_scope='session')
async def test_request_authorise_revoke_affiliation(
        uow_factory,
        team_tree_build_context
):
    user_id_1 = team_tree_build_context['user_id_1']
    user_id_2 = team_tree_build_context['user_id_2']
    team_input = TeamTreeBuilder.team_input()
    async with uow_factory.get_uow(user_id=user_id_1) as uow:
        team_tree = await uow.repositories.team_trees.create(team_input)
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id_2) as uow:
        team_tree = await uow.repositories.team_trees.get(team_id=team_tree.root.id)
        team_tree.request_affiliation(
            agent_id=user_id_2,
            team_id=team_tree.root.id,
            access=Access.READ,
            user_id=user_id_2,
            heritable=True
        )
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id_1) as uow:
        team_tree = await uow.repositories.team_trees.get(team_id=team_tree.root.id)
        team_tree.authorise_affiliation(
            agent_id=user_id_1,
            team_id=team_tree.root.id,
            access=Access.READ,
            user_id=user_id_2,
            heritable=True
        )
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id_1) as uow:
        team_tree = await uow.repositories.team_trees.get(team_id=team_tree.root.id)
        assert user_id_2 in team_tree.get_affiliates(
            team_tree.root.id, access=Access.READ, authorisation=Authorisation.AUTHORISED
        )
        team_tree.revoke_affiliation(
            agent_id=user_id_1,
            team_id=team_tree.root.id,
            access=Access.READ,
            user_id=user_id_2
        )
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id_1) as uow:
        team_tree = await uow.repositories.team_trees.get(team_id=team_tree.root.id)
        assert user_id_2 not in team_tree.get_affiliates(team_tree.root.id, access=Access.READ)

@pytest.mark.asyncio(loop_scope="session")
async def test_extend_then_remove(
        uow_factory,
        team_tree_build_context
):
    root_team_input = TeamTreeBuilder.team_input()
    child_team_input = TeamTreeBuilder.team_input()
    user_id = team_tree_build_context['user_id']
    async with uow_factory.get_uow(user_id=user_id) as uow:
        team_tree = await uow.repositories.team_trees.create(root_team_input)
        team_tree.add_team(child_team_input, parent_id=team_tree.root.id)
        await uow.commit()
        child_id = team_tree.get_children(team_tree.root.id)[0]

    async with uow_factory.get_uow(user_id=user_id) as uow:
        team_tree = await uow.repositories.team_trees.get(team_id=child_id)
        team_tree.remove_team(child_id)
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        team_tree = await uow.repositories.team_trees.get(team_id=team_tree.root.id)
        assert team_tree.size == 1

@pytest.mark.asyncio(loop_scope="session")
async def test_edit_team_name(
        uow_factory,
        team_tree_build_context
):
    team_input_1 = TeamTreeBuilder.team_input()
    team_input_2 = TeamTreeBuilder.team_input()
    user_id = team_tree_build_context['user_id']
    async with uow_factory.get_uow(user_id=user_id) as uow:
        team_tree = await uow.repositories.team_trees.create(team_input_1)
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        team_tree = await uow.repositories.team_trees.get(team_id=team_tree.root.id)
        team_tree.root.name = team_input_2.name
        team_tree.root.fullname = team_input_2.fullname
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        team_tree = await uow.repositories.team_trees.get(team_id=team_tree.root.id)
        assert team_tree.root.name == team_input_2.name
        assert team_tree.root.fullname == team_input_2.fullname

@pytest.mark.asyncio(loop_scope="session")
async def test_move_team(
        uow_factory,
        team_tree_build_context
):
    user_id = team_tree_build_context['user_id']
    team_input_1 = TeamTreeBuilder.team_input()
    team_input_2 = TeamTreeBuilder.team_input()
    team_input_3 = TeamTreeBuilder.team_input()
    async with uow_factory.get_uow(user_id=user_id) as uow:
        team_tree = await uow.repositories.team_trees.create(team_input_1)
        team_tree.add_team(team_input_2, parent_id=team_tree.root.id)
        team_tree.add_team(team_input_3, parent_id=team_tree.root.id)
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        team_tree = await uow.repositories.team_trees.get(team_id=team_tree.root.id)
        team_2 = team_tree.get_team(team_input_2.name)
        team_3 = team_tree.get_team(team_input_3.name)
        team_tree.change_source(team_3.id, team_2.id)
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        team_tree = await uow.repositories.team_trees.get(team_id=team_tree.root.id)
        assert team_2.id in team_tree._graph.successors(team_tree.root.id)
        assert team_3.id in team_tree._graph.successors(team_2.id)

@pytest.mark.asyncio(loop_scope="session")
async def test_split_and_merge_team_tree(
        uow_factory,
        team_tree_build_context
):
    user_id = team_tree_build_context['user_id']
    team_input_1 = TeamTreeBuilder.team_input()
    team_input_2 = TeamTreeBuilder.team_input()
    team_input_3 = TeamTreeBuilder.team_input()
    async with uow_factory.get_uow(user_id=user_id) as uow:
        team_tree_1 = await uow.repositories.team_trees.create(team_input_1)
        team_tree_1.add_team(team_input_2, parent_id=team_tree_1.root.id)
        team_tree_1.add_team(team_input_3, parent_id=team_tree_1.root.id)
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        team_tree_1 = await uow.repositories.team_trees.get(team_id=team_tree_1.root.id)
        team_3 = team_tree_1.get_team(team_input_3.name)
        #todo for proper typing of split (and for other purposes) we need abstract base types for each repository
        # currently we only have the neo4j implementations and the generic base and controlled types
        await uow.repositories.team_trees.split(team_3.id)
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        team_tree_1 = await uow.repositories.team_trees.get(team_id=team_tree_1.root.id)
        team_tree_2 = await uow.repositories.team_trees.get(team_id=team_3.id)
        assert team_tree_1.size == 2
        assert team_tree_2.size == 1
        # merge by adding team
        team_tree_1.add_team(team_tree_2.root, parent_id=team_tree_1.root.id)
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        team_tree_1 = await uow.repositories.team_trees.get(team_id=team_tree_1.root.id)
        assert team_tree_1.size == 3
