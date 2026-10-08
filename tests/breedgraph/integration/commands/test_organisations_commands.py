import pytest

from breedgraph.custom_exceptions import ProtectedNodeError
from breedgraph.domain.commands.accounts import SetWriteTeam
from breedgraph.domain.commands.organisations import CreateTeam, DeleteTeam
from breedgraph.domain.model.control_transfers import ControlledEntity
from breedgraph.domain.model.controls import Access, ControlledModelLabel

from tests.breedgraph.scenarios.account_builder import AccountBuilder
from tests.breedgraph.scenarios.organisation_builder import OrganisationBuilder
from tests.breedgraph.scenarios.program_builder import ProgramBuilder


async def child_team(bus, uow_factory, user_id: int, parent_id: int) -> int:
    name = OrganisationBuilder.team_input().name
    await bus.handle(CreateTeam(agent_id=user_id, name=name, parent=parent_id))
    async with uow_factory.get_uow(user_id=user_id) as uow:
        organisation = await uow.repositories.organisations.get(team_id=parent_id)
        [team_id] = [team.id for team in organisation.teams if team.name == name]
    organisation_builder = OrganisationBuilder(uow_factory)
    for access in Access:
        await organisation_builder.authorise_access(user_id=user_id, team_id=team_id, access=access)
    return team_id


async def create_program(uow_factory, user_id: int, team_id: int) -> ControlledEntity:
    async with uow_factory.get_uow(user_id=user_id, write_team=team_id) as uow:
        program = await uow.repositories.programs.create(ProgramBuilder.program_input())
        await uow.commit()
    return ControlledEntity(label=ControlledModelLabel.PROGRAM, id=program.id)


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_team_that_controls_entities_is_refused(bus, uow_factory, isolated_state):
    account = await AccountBuilder(uow_factory).account_with_affiliations()
    user_id = account['user_id']
    team_id = await child_team(bus, uow_factory, user_id, account['team_id'])
    await create_program(uow_factory, user_id, team_id)

    with pytest.raises(ProtectedNodeError, match="controls entities"):
        await bus.handle(DeleteTeam(agent_id=user_id, team_id=team_id))

    async with uow_factory.get_uow(user_id=user_id) as uow:
        organisation = await uow.repositories.organisations.get(team_id=account['team_id'])
        assert team_id in [team.id for team in organisation.teams]


@pytest.mark.asyncio(loop_scope="session")
async def test_deleted_team_keeps_control_history(bus, uow_factory, isolated_state):
    account = await AccountBuilder(uow_factory).account_with_affiliations()
    user_id = account['user_id']
    root_id = account['team_id']
    team_id = await child_team(bus, uow_factory, user_id, root_id)
    program = await create_program(uow_factory, user_id, team_id)
    await bus.handle(SetWriteTeam(user_id=user_id, team_id=team_id))

    # Move control to the root team, then delete the child team
    async with uow_factory.get_uow(user_id=user_id) as uow:
        await uow.controls.offer_transfer(
            entities=[program], from_teams={team_id}, recipient_team=root_id, to_teams={root_id}
        )
        await uow.commit()
    await bus.handle(DeleteTeam(agent_id=user_id, team_id=team_id))

    async with uow_factory.get_uow(user_id=user_id) as uow:
        # The team is no longer part of the organisation or the user's access
        organisation = await uow.repositories.organisations.get(team_id=root_id)
        assert team_id not in [team.id for team in organisation.teams]
        assert await uow.repositories.organisations.get(team_id=team_id) is None
        assert all(team_id not in teams for teams in uow.controls.access_teams.values())

        # Controls of the program are unaffected
        controller = await uow.controls.get_controller(program.label, program.id)
        assert controller.teams == {root_id}

        # The deleted team keeps its control history and records its parent
        result = await uow.tx.run(
            "MATCH (team:DeletedTeam {id: $team_id}) "
            "OPTIONAL MATCH (team)-[:CONTROLS]->(:TeamPrograms)-[:CONTROLS]->(control:Control)"
            "-[:CONTROLS]->(:Program {id: $program_id}) "
            "WITH team, control ORDER BY control.sequence "
            "RETURN team.parent AS parent, team.deleted_by AS deleted_by, "
            "team.deleted_at IS NOT NULL AS deleted, collect(control.ended) AS ended",
            team_id=team_id,
            program_id=program.id
        )
        record = await result.single()
        assert record['parent'] == root_id
        assert record['deleted_by'] == user_id
        assert record['deleted']
        assert record['ended'] == [True]

        account_stored = await uow.repositories.accounts.get(user_id=user_id)
        assert account_stored.user.default_write_team is None


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_team_cancels_pending_transfers(bus, uow_factory, isolated_state):
    account = await AccountBuilder(uow_factory).account_with_affiliations()
    user_id = account['user_id']
    root_id = account['team_id']
    team_id = await child_team(bus, uow_factory, user_id, root_id)

    shared_program = await create_program(uow_factory, user_id, team_id)
    root_program = await create_program(uow_factory, user_id, root_id)
    async with uow_factory.get_uow(user_id=user_id) as uow:
        # Share control of the first program with the root team, then offer it from the child team
        await uow.controls.offer_transfer(
            entities=[shared_program], from_teams={team_id}, recipient_team=root_id,
            keep_from_teams=True, to_teams={root_id}
        )
        offered_from = await uow.controls.offer_transfer(
            entities=[shared_program], from_teams={team_id}, recipient_team=root_id
        )
        # Offer the second program to the child team
        offered_to = await uow.controls.offer_transfer(
            entities=[root_program], from_teams={root_id}, recipient_team=team_id
        )
        # The child team gives up its control, so it can be deleted
        await uow.controls.renounce_controls(entities=[shared_program], team_ids={team_id})
        await uow.commit()

    await bus.handle(DeleteTeam(agent_id=user_id, team_id=team_id))

    async with uow_factory.get_uow(user_id=user_id) as uow:
        for transfer_id in (offered_from.id, offered_to.id):
            transfer = await uow.controls.get_transfer(transfer_id)
            assert transfer.status.value == 'CANCELLED'
            assert transfer.cancelled_by == user_id
            assert transfer.cancelled_at is not None
