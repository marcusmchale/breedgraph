from src.breedgraph.service_layer import unit_of_work
from src.breedgraph.domain import commands
from src.breedgraph.domain.model.organisations import (
    TeamInput, TeamStored, Organisation,
    Authorisation, Access, Affiliation,
)
from src.breedgraph.custom_exceptions import (
    IdentityExistsError,
    UnauthorisedOperationError,
    ProtectedNodeError
)

import logging


logger = logging.getLogger(__name__)

async def add_team(
        cmd: commands.organisations.AddTeam,
        uow: unit_of_work.Neo4jUnitOfWork
):
    async with uow.get_repositories() as uow:
        account = await uow.accounts.get(user_id=cmd.user)

        for a in account.affiliations:
            if a.access == Access.ADMIN and a.authorisation == Authorisation.AUTHORISED:
               break
        else:
            raise UnauthorisedOperationError("Only admins can add teams")

        team_input = TeamInput(
            name=cmd.name,
            fullname=cmd.fullname if cmd.fullname else cmd.name,
            parent=cmd.parent
        )

        if cmd.parent is not None:
            organisation = await uow.organisations.get(team_id=team_input.parent)
            parent = organisation.nodes[team_input.parent]
            if not account.user.id in parent.admins:
                raise UnauthorisedOperationError("Only admins for the parent team can add a child team")

            for t in parent.children:
                team = organisation.nodes[t]
                if team.name.casefold() == team_input.name.casefold():
                    raise IdentityExistsError("The chosen parent team already has a child team with this name")

            organisation._add_node(team_input)
            await uow.organisations.update_seen()
            # get the team ID to add an admin affiliation to the account
            updated_organisation = await uow.organisations.get(team_id=team_input.parent)
            stored_team: TeamStored = updated_organisation.get_node(
                name=team_input.name,
                parent_id=team_input.parent
            )
        else:
            async for organisation in uow.organisations.get_all():
                if organisation.root.name.casefold() == cmd.name.casefold():
                    raise IdentityExistsError("The chosen parent team already has a child team with this name")

            organisation = await uow.organisations.create(team_input)
            stored_team = organisation.root

        account.affiliations.append(
                Affiliation(
                    team=stored_team.id,
                    access=Access.ADMIN,
                    authorisation=Authorisation.AUTHORISED,
                    heritable=True
                )
        )
        await uow.commit()

async def remove_team(
        cmd: commands.organisations.RemoveTeam,
        uow: unit_of_work.Neo4jUnitOfWork
):
    async with uow.get_repositories() as uow:
        organisation: Organisation = await uow.organisations.get(team_id=cmd.team)
        team = organisation.nodes[cmd.team]

        if not cmd.user in team.admins:
            raise UnauthorisedOperationError("Only admins for the given team can remove it")

        if team.children:
            raise ProtectedNodeError("Cannot remove a team with children")

        organisation.remove_node(team.id)

        await uow.commit()

async def edit_team(
        cmd: commands.organisations.UpdateTeam,
        uow: unit_of_work.Neo4jUnitOfWork
):
    async with uow.get_repositories() as uow:
        organisation: Organisation = await uow.organisations.get(team_id=cmd.team)
        team = organisation.nodes[cmd.team]

        if not cmd.user in team.admins:
            raise UnauthorisedOperationError("Only admins for the given team can remove it")

        if cmd.name is not None:
            team.name = cmd.name
        if cmd.fullname is not None:
            team.fullname = cmd.fullname

        await uow.commit()