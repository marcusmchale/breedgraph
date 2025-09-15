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
    async with uow.get_uow(user_id=cmd.user) as uow:
        team_input = TeamInput(
            name=cmd.name,
            fullname=cmd.fullname if cmd.fullname else cmd.name
        )
        if cmd.parent is None:
            await uow.repositories.organisations.create(team_input)

        else:
            org: Organisation = await uow.repositories.organisations.get(team_id=cmd.parent)
            if not cmd.user in org.get_affiliates(cmd.parent, access=Access.ADMIN):
                raise UnauthorisedOperationError("Only admins for the given parent team may add child teams")

            org.add_team(team_input, parent_id=cmd.parent)
            #await uow.repositories.organisations.update_seen()
        await uow.commit()

@handlers.command_handler()
async def delete_team(
        cmd: commands.organisations.DeleteTeam,
        uow: AbstractUnitOfWork
):
    async with uow.get_uow(user_id=cmd.user) as uow:
        organisation: Organisation = await uow.repositories.organisations.get(team_id=cmd.team)

        if not cmd.user in organisation.get_affiliates(cmd.team, Access.ADMIN):
            raise UnauthorisedOperationError("Only admins for the given team can remove it")

        if organisation.get_sinks(cmd.team):
            raise ProtectedNodeError("Cannot remove a team with children")

        organisation.remove_team(cmd.team)

        await uow.commit()

@handlers.command_handler()
async def update_team(
        cmd: commands.organisations.UpdateTeam,
        uow: AbstractUnitOfWork
):
    async with uow.get_uow(user_id=cmd.user) as uow:
        organisation: Organisation = await uow.repositories.organisations.get(team_id=cmd.team)
        team = organisation.get_team(cmd.team)
        if not cmd.user in organisation.get_affiliates(cmd.team, Access.ADMIN):
            raise UnauthorisedOperationError("Only admins for the given team can update team details")

        if cmd.name is not None:
            team.name = cmd.name
        if cmd.fullname is not None:
            team.fullname = cmd.fullname

        await uow.commit()