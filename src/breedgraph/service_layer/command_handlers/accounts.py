from itsdangerous import URLSafeTimedSerializer, SignatureExpired
from werkzeug.exceptions import Unauthorized

from src.breedgraph import config
from src.breedgraph.service_layer import unit_of_work
from src.breedgraph.domain import commands, events
from src.breedgraph.domain.model.accounts import (
    UserInput, UserStored,
    Authorisation, Access,
    Affiliation,
    AccountInput, AccountStored
)
from src.breedgraph.domain.model.organisations import (
    TeamInput, TeamStored,
    OrganisationInput, OrganisationStored
)
from src.breedgraph.custom_exceptions import (
    NoResultFoundError,
    IdentityExistsError,
    ProtectedNodeError,
    UnauthorisedOperationError
)

import logging


logger = logging.getLogger(__name__)

async def add_first_account(
        cmd: commands.accounts.AddFirstAccount,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with (uow):
        async for _ in uow.accounts.get_all():
            raise UnauthorisedOperationError("This operation is only permitted when no accounts have been registered")

        user = UserInput(
            name=cmd.name,
            fullname=cmd.fullname if cmd.fullname else cmd.name,
            email=cmd.email,
            password_hash=cmd.password_hash
        )

        team = TeamInput(
            name=cmd.team_name,
            fullname=cmd.team_fullname if cmd.team_fullname else cmd.team_name
        )

        organisation: OrganisationInput = OrganisationInput(teams=[team])
        organisation: OrganisationStored = await uow.organisations.create(organisation)

        account: AccountInput = AccountInput(user=user)
        account: AccountStored = await uow.accounts.create(account)
        account.affiliations.append(Affiliation(
                team=organisation.root.id,
                access=Access.ADMIN,
                authorisation = Authorisation.AUTHORISED
            )
        )
        account.events.append(events.accounts.AccountAdded(user=account.user.id))
        await uow.commit()

async def add_account(
        cmd: commands.accounts.AddAccount,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow:

        # Registration email must be included in the allowed emails of some other account
        async for account in uow.accounts.get_all(
                access_types=[Access.ADMIN],
                authorisations=[Authorisation.AUTHORISED]
        ):
            account: AccountStored
            if cmd.email.casefold() in [i.casefold() for i in account.allowed_emails]:
                break
        else:
            raise UnauthorisedOperationError("Email is not allowed")

        # Check for accounts with same email but not verified
        existing_email: AccountStored = await uow.accounts.get_by_email(cmd.email)

        if existing_email is not None:
            if not existing_email.user.email_verified:
                await uow.accounts.remove(existing_email)
            else:
                raise UnauthorisedOperationError("This email address is already registered and verified")

        # Check for accounts And whether the name is already taken
        existing_name: AccountStored = await uow.accounts.get_by_name(cmd.name)
        if existing_name is not None:
            raise IdentityExistsError(f"Username already taken")

        user = UserInput(
            name=cmd.name,
            fullname=cmd.fullname if cmd.fullname else cmd.name,
            email=cmd.email,
            password_hash=cmd.password_hash
        )

        account: AccountInput = AccountInput(user=user)
        account: AccountStored = await uow.accounts.create(account)

        account.events.append(events.accounts.AccountAdded(user=account.user.id))
        await uow.commit()

async def verify_email(
        cmd: commands.accounts.VerifyEmail,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow:
        ts = URLSafeTimedSerializer(config.SECRET_KEY)

        try:
            uid = ts.loads(cmd.token, salt=config.VERIFY_TOKEN_SALT, max_age=config.TOKEN_EXPIRES_MINUTES * 60)
        except SignatureExpired as e:
            logger.debug(f"Attempt to use expired token, signed: {e.date_signed}")
            raise UnauthorisedOperationError("This token has expired")

        account = await uow.accounts.get(uid)
        if account is None:
            raise NoResultFoundError

        account.user.email_verified = True

        # now remove allowed emails, this results in the ALLOWED_REGISTRATION relationship being created
        async for admin in uow.accounts.get_all(access_types=[Access.ADMIN], authorisations=[Authorisation.AUTHORISED]):
            for e in admin.allowed_emails:
                if e.casefold() == account.user.email.casefold():
                    admin.allowed_emails.remove(e)

        account.events.append(events.accounts.EmailVerified(user=account.user.id))
        await uow.commit()

async def login(
        cmd: commands.accounts.Login,
        uow: unit_of_work.AbstractUnitOfWork
):
    # todo logic to record login events etc.
    pass
    # raise NotImplementedError

async def add_email(
        cmd: commands.accounts.AddEmail,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow:
        if await uow.accounts.get_by_email(cmd.email):
            raise IdentityExistsError("This email is already registered to an account")

        account = await uow.accounts.get(cmd.user)

        account.allowed_emails.append(cmd.email)
        account.events.append(events.accounts.EmailAdded(email=cmd.email))
        await uow.commit()

async def remove_email(
        cmd: commands.accounts.RemoveEmail,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow:
        account = await uow.accounts.get(cmd.user)
        try:
            account.allowed_emails.remove(cmd.email)
        except ValueError:
            raise NoResultFoundError("Email not found among those allowed by this account")
        account.events.append(events.accounts.EmailRemoved(email=cmd.email))
        await uow.commit()


async def add_team(
        cmd: commands.accounts.AddTeam,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow:
        account = await uow.accounts.get(cmd.user)

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
            organisation = await uow.organisations.get(team_input.parent)
            parent = organisation.get_team(team_input.parent)
            if not account.user.id in parent.admins:
                raise UnauthorisedOperationError("Only admins for the parent team can add a child team")

            for t in parent.children:
                team = organisation.get_team(t)
                if team.name.casefold() == team_input.name.casefold():
                    raise IdentityExistsError("The chosen parent team already has a child team with this name")

            organisation.teams.append(team_input)
            await uow.organisations.update_seen()
            # get the team ID to add an admin affiliation to the account
            updated_organisation = await uow.organisations.get(team_input.parent)
            stored_team: TeamStored = updated_organisation.get_team_by_name_and_parent(
                name=team_input.name,
                parent=team_input.parent
            )
        else:
            async for organisation in uow.organisations.get_all():
                if organisation.root.name.casefold() == cmd.name.casefold():
                    raise IdentityExistsError("The chosen parent team already has a child team with this name")

            organisation = await uow.organisations.create(OrganisationInput(teams=[team_input]))
            stored_team = organisation.root


        account.affiliations.append(
                Affiliation(
                    team=stored_team.id,
                    access=Access.ADMIN,
                    authorisation=Authorisation.AUTHORISED
                )
        )
        await uow.commit()


async def remove_team(
        cmd: commands.accounts.RemoveTeam,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow:
        account = await uow.accounts.get(cmd.user)

        for a in account.affiliations:
            if a.access == Access.ADMIN and a.authorisation == Authorisation.AUTHORISED:
               break
        else:
            raise UnauthorisedOperationError("Only admins can remove teams")

        organisation: OrganisationStored = await uow.organisations.get(cmd.team)
        team = organisation.get_team(cmd.team)

        if not cmd.user in team.admins:
            raise UnauthorisedOperationError("Only admins for the given team can remove it")

        if team.children:
            raise ProtectedNodeError("Cannot remove a team with children")

        organisation.teams.remove(team)

        await uow.commit()

async def request_affiliation(
        cmd: commands.accounts.RequestAffiliation,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow:
        account = await uow.accounts.get(cmd.user)
        organisation = await uow.organisations.get(cmd.team)
        team = organisation.get_team(cmd.team)

        for a in account.affiliations:
            if a.team == cmd.team and a.access == cmd.access:
                if a.authorisation in [Authorisation.RETIRED, Authorisation.DENIED]:
                    a.authorisation = Authorisation.REQUESTED
                    await uow.commit()
                    return
                elif a.authorisation == Authorisation.REQUESTED:
                    logger.debug("Repeated request, do nothing")
                    return
                elif a.authorisation == Authorisation.AUTHORISED:
                    logger.debug("Request already approved, do nothing")
                    return

        if cmd.user in team.admins:
            authorisation = Authorisation.AUTHORISED
        else:
            authorisation = Authorisation.REQUESTED
            account.events.append(
                events.accounts.AffiliationRequested(
                    user=cmd.user,
                    team=cmd.team,
                    access=Access[cmd.access]
                )
            )
        affiliation = Affiliation(
            team= cmd.team,
            authorisation=authorisation,
            access=Access[cmd.access]
        )
        account.affiliations.append(affiliation)
        await uow.commit()

async def approve_affiliation(
        cmd: commands.accounts.ApproveAffiliation,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow:
        requesting_account = await uow.accounts.get(cmd.user)
        organisation = await uow.organisations.get(cmd.team)
        team = organisation.get_team(cmd.team)
        if not cmd.admin in team.admins:
            raise UnauthorisedOperationError("Only an admins for the given team can perform this operation")
        if not requesting_account.user.id in team.read_requests:
            raise UnauthorisedOperationError("The request to apply this affiliation was not found")
        affiliation = Affiliation(
            team=cmd.team,
            access=Access[cmd.access],
            authorisation=Authorisation.AUTHORISED,
            heritable=cmd.heritable
        )
        requesting_account.affiliations.append(affiliation)
        requesting_account.events.append(events.accounts.AffiliationApproved(
            user=cmd.user,
            team=cmd.team,
            access=cmd.access
        ))
        await uow.commit()

async def remove_affiliation(
        cmd: commands.accounts.RemoveAffiliation,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow:
        organisation = await uow.organisations.get(cmd.team)
        team = organisation.get_team(cmd.team)
        if not cmd.admin in team.admins:
            raise UnauthorisedOperationError("Only an admins for the given team can perform this operation")
        account = await uow.accounts.get(cmd.user)
        for a in account.affiliations:
            if all([
                a.team == cmd.team,
                a.access == cmd.access
            ]):
                account.affiliations.remove(a)
                break
        await uow.commit()
