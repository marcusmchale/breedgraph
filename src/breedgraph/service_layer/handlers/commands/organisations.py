from src.breedgraph.domain import commands
from src.breedgraph.domain.model.organisations import (
    TeamInput, TeamStored, Organisation,
    Authorisation, Access, Affiliation,
)

from src.breedgraph.service_layer.infrastructure import AbstractUnitOfWork, unit_of_work

from src.breedgraph.custom_exceptions import (
    UnauthorisedOperationError,
    ProtectedNodeError
)

from ..registry import handlers

import logging
logger = logging.getLogger(__name__)

@handlers.command_handler()
async def create_team(
        cmd: commands.organisations.CreateTeam,
        uow: AbstractUnitOfWork
):
    # strange behaviour here, possibly async conflict but needs dissecting
    # three times we are calling get_access_teams in calling get_uow....
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        if cmd.parent is not None:
            access_teams = uow.controls.access_teams
            if cmd.parent not in access_teams.get(Access.ADMIN):
                raise UnauthorisedOperationError("Only admins for the given parent team may add child teams")

        team_input = TeamInput(
            name=cmd.name,
            fullname=cmd.fullname if cmd.fullname else cmd.name
        )
        if cmd.parent is None:
            await uow.repositories.organisations.create(team_input)
        else:
            org: Organisation = await uow.repositories.organisations.get(team_id=cmd.parent)
            org.add_team(team_input, parent_id=cmd.parent)
            #await uow.repositories.organisations.update_seen()
        await uow.commit()

@handlers.command_handler()
async def delete_team(
        cmd: commands.organisations.DeleteTeam,
        uow: AbstractUnitOfWork
):
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        access_teams = uow.controls.access_teams
        if not cmd.team_id in access_teams.get(Access.ADMIN):
            raise UnauthorisedOperationError("Only admins for the given team can remove it")

        organisation: Organisation = await uow.repositories.organisations.get(team_id=cmd.team_id)
        if organisation.get_sinks(cmd.team_id):
            raise ProtectedNodeError("Cannot remove a team with children")

        organisation.remove_team(cmd.team_id)
        await uow.commit()

@handlers.command_handler()
async def update_team(
        cmd: commands.organisations.UpdateTeam,
        uow: AbstractUnitOfWork
):
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        access_teams = uow.controls.access_teams
        if not cmd.team_id in access_teams.get(Access.ADMIN):
            raise UnauthorisedOperationError("Only admins for the given team can update team details")

        organisation: Organisation = await uow.repositories.organisations.get(team_id=cmd.team_id)
        team = organisation.get_team(cmd.team_id)
        if cmd.name is not None:
            team.name = cmd.name
        if cmd.fullname is not None:
            team.fullname = cmd.fullname
        await uow.commit()