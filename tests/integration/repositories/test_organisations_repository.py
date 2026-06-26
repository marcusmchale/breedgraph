import pytest

from breedgraph.domain.model.organisations import Access, Authorisation
from breedgraph.custom_exceptions import NoResultFoundError

from tests.scenarios.organisation_builder import OrganisationBuilder

@pytest.mark.asyncio(loop_scope="session")
async def test_create_get_extend(
        uow_factory,
        organisation_build_context
):
    team_input_1 = OrganisationBuilder.team_input()
    team_input_2 = OrganisationBuilder.team_input()
    user_id = organisation_build_context['user_id']
    async with uow_factory.get_uow(user_id=user_id) as uow:
        organisation = await uow.repositories.organisations.create(team_input_1)
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        organisation = await uow.repositories.organisations.get(team_id=organisation.root.id)
        assert organisation.root.name == team_input_1.name

        async for organisation in uow.repositories.organisations.get_all():
            if organisation.root.name == team_input_1.name:
                break
        else:
            raise NoResultFoundError("Organisation not retrieved by get all")

        # Add a child
        organisation.add_team(team_input_2, parent_id=organisation.root.id)
        await uow.repositories.organisations.update_seen()

        # get child id
        child_id = organisation.get_children(organisation.root.id)[0]
        # retrieve from db by child ID
        retrieved_from_child_id = await uow.repositories.organisations.get(team_id=child_id)
        assert retrieved_from_child_id.root.id == organisation.root.id
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
        organisation_build_context
):
    user_id_1 = organisation_build_context['user_id_1']
    user_id_2 = organisation_build_context['user_id_2']
    team_input = OrganisationBuilder.team_input()
    async with uow_factory.get_uow(user_id=user_id_1) as uow:
        organisation = await uow.repositories.organisations.create(team_input)
        assert user_id_1 in organisation.get_affiliates(organisation.root.id)
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id_2) as uow:
        organisation = await uow.repositories.organisations.get(team_id=organisation.root.id)
        organisation.request_affiliation(
            agent_id=user_id_2,
            team_id=organisation.root.id,
            access=Access.READ,
            user_id=user_id_2,
            heritable=True
        )
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id_1) as uow:
        organisation = await uow.repositories.organisations.get(team_id=organisation.root.id)
        assert user_id_2 in organisation.get_affiliates(
            organisation.root.id,
            access=Access.READ,
            authorisation=Authorisation.REQUESTED
        )
        organisation.remove_affiliation(
            agent_id=user_id_1,
            team_id=organisation.root.id,
            access=Access.READ,
            user_id=user_id_2
        )
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id_1) as uow:
        organisation = await uow.repositories.organisations.get(team_id=organisation.root.id)
        assert user_id_2 not in organisation.get_affiliates(organisation.root.id, access=Access.READ, authorisation=Authorisation.REQUESTED)

@pytest.mark.asyncio(loop_scope='session')
async def test_request_authorise_revoke_affiliation(
        uow_factory,
        organisation_build_context
):
    user_id_1 = organisation_build_context['user_id_1']
    user_id_2 = organisation_build_context['user_id_2']
    team_input = OrganisationBuilder.team_input()
    async with uow_factory.get_uow(user_id=user_id_1) as uow:
        organisation = await uow.repositories.organisations.create(team_input)
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id_2) as uow:
        organisation = await uow.repositories.organisations.get(team_id=organisation.root.id)
        organisation.request_affiliation(
            agent_id=user_id_2,
            team_id=organisation.root.id,
            access=Access.READ,
            user_id=user_id_2,
            heritable=True
        )
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id_1) as uow:
        organisation = await uow.repositories.organisations.get(team_id=organisation.root.id)
        organisation.authorise_affiliation(
            agent_id=user_id_1,
            team_id=organisation.root.id,
            access=Access.READ,
            user_id=user_id_2,
            heritable=True
        )
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id_1) as uow:
        organisation = await uow.repositories.organisations.get(team_id=organisation.root.id)
        assert user_id_2 in organisation.get_affiliates(
            organisation.root.id, access=Access.READ, authorisation=Authorisation.AUTHORISED
        )
        organisation.revoke_affiliation(
            agent_id=user_id_1,
            team_id=organisation.root.id,
            access=Access.READ,
            user_id=user_id_2
        )
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id_1) as uow:
        organisation = await uow.repositories.organisations.get(team_id=organisation.root.id)
        assert user_id_2 not in organisation.get_affiliates(organisation.root.id, access=Access.READ)

@pytest.mark.asyncio(loop_scope="session")
async def test_extend_then_remove(
        uow_factory,
        organisation_build_context
):
    root_team_input = OrganisationBuilder.team_input()
    child_team_input = OrganisationBuilder.team_input()
    user_id = organisation_build_context['user_id']
    async with uow_factory.get_uow(user_id=user_id) as uow:
        organisation = await uow.repositories.organisations.create(root_team_input)
        organisation.add_team(child_team_input, parent_id=organisation.root.id)
        await uow.commit()
        child_id = organisation.get_children(organisation.root.id)[0]

    async with uow_factory.get_uow(user_id=user_id) as uow:
        organisation = await uow.repositories.organisations.get(team_id=child_id)
        organisation.remove_team(child_id)
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        organisation = await uow.repositories.organisations.get(team_id=organisation.root.id)
        assert organisation.size == 1

@pytest.mark.asyncio(loop_scope="session")
async def test_edit_team_name(
        uow_factory,
        organisation_build_context
):
    team_input_1 = OrganisationBuilder.team_input()
    team_input_2 = OrganisationBuilder.team_input()
    user_id = organisation_build_context['user_id']
    async with uow_factory.get_uow(user_id=user_id) as uow:
        organisation = await uow.repositories.organisations.create(team_input_1)
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        organisation = await uow.repositories.organisations.get(team_id=organisation.root.id)
        organisation.root.name = team_input_2.name
        organisation.root.fullname = team_input_2.fullname
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        organisation = await uow.repositories.organisations.get(team_id=organisation.root.id)
        assert organisation.root.name == team_input_2.name
        assert organisation.root.fullname == team_input_2.fullname

@pytest.mark.asyncio(loop_scope="session")
async def test_move_team(
        uow_factory,
        organisation_build_context
):
    user_id = organisation_build_context['user_id']
    team_input_1 = OrganisationBuilder.team_input()
    team_input_2 = OrganisationBuilder.team_input()
    team_input_3 = OrganisationBuilder.team_input()
    async with uow_factory.get_uow(user_id=user_id) as uow:
        organisation = await uow.repositories.organisations.create(team_input_1)
        organisation.add_team(team_input_2, parent_id=organisation.root.id)
        organisation.add_team(team_input_3, parent_id=organisation.root.id)
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        organisation = await uow.repositories.organisations.get(team_id=organisation.root.id)
        team_2 = organisation.get_team(team_input_2.name)
        team_3 = organisation.get_team(team_input_3.name)
        organisation.change_source(team_3.id, team_2.id)
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        organisation = await uow.repositories.organisations.get(team_id=organisation.root.id)
        assert team_2.id in organisation._graph.successors(organisation.root.id)
        assert team_3.id in organisation._graph.successors(team_2.id)

@pytest.mark.asyncio(loop_scope="session")
async def test_split_and_merge_organisation(
        uow_factory,
        organisation_build_context
):
    user_id = organisation_build_context['user_id']
    team_input_1 = OrganisationBuilder.team_input()
    team_input_2 = OrganisationBuilder.team_input()
    team_input_3 = OrganisationBuilder.team_input()
    async with uow_factory.get_uow(user_id=user_id) as uow:
        organisation_1 = await uow.repositories.organisations.create(team_input_1)
        organisation_1.add_team(team_input_2, parent_id=organisation_1.root.id)
        organisation_1.add_team(team_input_3, parent_id=organisation_1.root.id)
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        organisation_1 = await uow.repositories.organisations.get(team_id=organisation_1.root.id)
        team_3 = organisation_1.get_team(team_input_3.name)
        #todo for proper typing of split (and for other purposes) we need abstract base types for each repository
        # currently we only have the neo4j implementations and the generic base and controlled types
        await uow.repositories.organisations.split(team_3.id)
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        organisation_1 = await uow.repositories.organisations.get(team_id=organisation_1.root.id)
        organisation_2 = await uow.repositories.organisations.get(team_id=team_3.id)
        assert organisation_1.size == 2
        assert organisation_2.size == 1
        # merge by adding team
        organisation_1.add_team(organisation_2.root, parent_id=organisation_1.root.id)
        await uow.commit()

    async with uow_factory.get_uow(user_id=user_id) as uow:
        organisation_1 = await uow.repositories.organisations.get(team_id=organisation_1.root.id)
        assert organisation_1.size == 3
