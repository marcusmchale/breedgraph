from breedgraph.domain import commands
from breedgraph.domain.model.team_trees import (
    TeamInput, TeamStored, TeamTree,
    Authorisation, Affiliation,
)
from breedgraph.domain.model.controls import Access

from breedgraph.service_layer.infrastructure import AbstractUnitOfWorkFactory, unit_of_work

from breedgraph.custom_exceptions import (
    UnauthorisedOperationError,
    ProtectedNodeError
)

from ..registry import handlers

import logging
logger = logging.getLogger(__name__)

@handlers.command_handler()
async def create_team(
        cmd: commands.team_trees.CreateTeam,
        uow_factory: AbstractUnitOfWorkFactory
):
    # strange behaviour here, possibly async conflict but needs dissecting
    # three times we are calling get_access_teams in calling get_uow....
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        if cmd.parent is not None:
            access_teams = uow.controls.access_teams
            if cmd.parent not in access_teams.get(Access.ADMIN):
                raise UnauthorisedOperationError("Only admins for the given parent team may add child teams")

        team_input = TeamInput(
            name=cmd.name,
            fullname=cmd.fullname if cmd.fullname else cmd.name
        )
        if cmd.parent is None:
            org: TeamTree = await uow.repositories.team_trees.create(team_input)
        else:
            org: TeamTree = await uow.repositories.team_trees.get(team_id=cmd.parent)
            org.add_team(team_input, parent_id=cmd.parent)
            #await uow.repositories.team_trees.update_seen()
        await uow.commit()

@handlers.command_handler()
async def delete_team(
        cmd: commands.team_trees.DeleteTeam,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        access_teams = uow.controls.access_teams
        if not cmd.team_id in access_teams.get(Access.ADMIN):
            raise UnauthorisedOperationError("Only admins for the given team can remove it")

        team_tree: TeamTree = await uow.repositories.team_trees.get(team_id=cmd.team_id)
        if team_tree.get_sinks(cmd.team_id):
            raise ProtectedNodeError("Cannot remove a team with children")
        if await uow.guards.team_controls_entities(cmd.team_id):
            raise ProtectedNodeError("Cannot remove a team that controls entities, transfer or renounce its control first")

        await uow.controls.cancel_transfers_for_team(cmd.team_id)

        team_tree.remove_team(cmd.team_id)
        await uow.commit()

@handlers.command_handler()
async def update_team(
        cmd: commands.team_trees.UpdateTeam,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        access_teams = uow.controls.access_teams
        if not cmd.team_id in access_teams.get(Access.ADMIN):
            raise UnauthorisedOperationError("Only admins for the given team can update team details")

        team_tree: TeamTree = await uow.repositories.team_trees.get(team_id=cmd.team_id)
        team = team_tree.get_team(cmd.team_id)
        if cmd.name is not None:
            team.name = cmd.name
        if cmd.given('fullname'):
            team.fullname = cmd.given_text('fullname')
        await uow.commit()