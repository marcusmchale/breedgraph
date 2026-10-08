from breedgraph.domain import commands
from breedgraph.domain.model.organisations import (
    TeamInput, TeamStored, Organisation,
    Authorisation, Affiliation,
)
from breedgraph.domain.model.controls import Access

from breedgraph.service_layer.infrastructure import AbstractUnitOfWorkFactory, unit_of_work

from breedgraph import config
from breedgraph.custom_exceptions import (
    UnauthorisedOperationError,
    ProtectedNodeError,
    IllegalOperationError,
    NoResultFoundError
)

from ..registry import handlers

import logging
logger = logging.getLogger(__name__)

@handlers.command_handler()
async def create_team(
        cmd: commands.organisations.CreateTeam,
        uow_factory: AbstractUnitOfWorkFactory
):
    # strange behaviour here, possibly async conflict but needs dissecting
    # three times we are calling get_access_teams in calling get_uow....
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        if cmd.parent is not None:
            access_teams = uow.controls.access_teams
            if cmd.parent not in access_teams.get(Access.ADMIN):
                raise UnauthorisedOperationError("Only admins for the given parent team may add child teams")

        if cmd.legal_entity is not None and cmd.parent is not None:
            raise IllegalOperationError("A legal entity can only be declared on the root team of an organisation")

        team_input = TeamInput(
            name=cmd.name,
            fullname=cmd.fullname if cmd.fullname else cmd.name
        )
        if cmd.parent is None:
            org: Organisation = await uow.repositories.organisations.create(team_input)
            if cmd.legal_entity is not None:
                org.declare_legal_entity(
                    agent_id=cmd.agent_id,
                    team_id=org.get_root_id(),
                    current_terms_version=config.DATA_PROCESSING_TERMS_VERSION,
                    **cmd.legal_entity.model_dump()
                )
        else:
            org: Organisation = await uow.repositories.organisations.get(team_id=cmd.parent)
            org.add_team(team_input, parent_id=cmd.parent)
            #await uow.repositories.organisations.update_seen()
        await uow.commit()

@handlers.command_handler()
async def declare_legal_entity(
        cmd: commands.organisations.DeclareLegalEntity,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        organisation: Organisation = await uow.repositories.organisations.get(team_id=cmd.team_id)
        if organisation is None:
            raise NoResultFoundError(f"Team {cmd.team_id} not found")
        organisation.declare_legal_entity(
            agent_id=cmd.agent_id,
            team_id=cmd.team_id,
            current_terms_version=config.DATA_PROCESSING_TERMS_VERSION,
            **cmd.legal_entity.model_dump()
        )
        await uow.commit()

@handlers.command_handler()
async def delete_team(
        cmd: commands.organisations.DeleteTeam,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        access_teams = uow.controls.access_teams
        if not cmd.team_id in access_teams.get(Access.ADMIN):
            raise UnauthorisedOperationError("Only admins for the given team can remove it")

        organisation: Organisation = await uow.repositories.organisations.get(team_id=cmd.team_id)
        if organisation.get_sinks(cmd.team_id):
            raise ProtectedNodeError("Cannot remove a team with children")
        if await uow.guards.team_controls_entities(cmd.team_id):
            raise ProtectedNodeError("Cannot remove a team that controls entities, transfer or renounce its control first")

        await uow.controls.cancel_transfers_for_team(cmd.team_id)

        organisation.remove_team(cmd.team_id)
        await uow.commit()

@handlers.command_handler()
async def update_team(
        cmd: commands.organisations.UpdateTeam,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
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