from src.breedgraph.domain import commands, events
from src.breedgraph.domain.model.accounts import UserInput, AccountInput, AccountStored, OntologyRole
from src.breedgraph.domain.model.organisations import Authorisation, Access

from src.breedgraph.service_layer.infrastructure import AbstractUnitOfWork, AbstractAuthService

from src.breedgraph.custom_exceptions import (
    NoResultFoundError,
    IdentityExistsError,
    UnauthorisedOperationError, IllegalOperationError
)

from ..registry import handlers

import logging
logger = logging.getLogger(__name__)

@handlers.command_handler()
async def create_account(
        cmd: commands.accounts.CreateAccount,
        uow: AbstractUnitOfWork
):
    async with uow.get_uow() as uow:
        # First check if any accounts exist
        if await uow.views.check_any_account():
            # And if so, the email must be included in the allowed emails of some other account
            if not await uow.views.check_allowed_email(cmd.email):
                raise UnauthorisedOperationError("Please contact an existing user to be invited")
            ontology_role = OntologyRole.CONTRIBUTOR
        else:
            # first user to register is the first Ontology Admin
            # and is responsible for elevating other users to ADMIN/EDITOR privilege.
            ontology_role = OntologyRole.ADMIN

        # Check for accounts with same email but not verified
        existing_email: AccountStored = await uow.repositories.accounts.get(email=cmd.email)
        if existing_email is not None:
            # and if it exists but isn't verified
            if not existing_email.user.email_verified:
                # then allow removing the old one to replace it with the current registration attempt
                logger.debug("Removing an unverified account to replace it with a new one")
                await uow.repositories.accounts.remove(existing_email)
            else:
                # but if it is verified then raise an error
                raise UnauthorisedOperationError("This email address is already registered and verified")

        # Check for accounts with the same username. These should be unique
        existing_name: AccountStored = await uow.repositories.accounts.get(name=cmd.name)
        if existing_name is not None:
            raise IdentityExistsError(f"Username already taken")

        user = UserInput(
            name=cmd.name,
            fullname=cmd.fullname if cmd.fullname else cmd.name,
            email=cmd.email,
            password_hash=cmd.password_hash,
            ontology_role=ontology_role
        )

        account: AccountInput = AccountInput(user=user)
        await uow.repositories.accounts.create(account)
        await uow.commit()

@handlers.command_handler()
async def edit_user(
        cmd: commands.accounts.UpdateUser,
        uow: AbstractUnitOfWork
):
    async with uow.get_uow() as uow:
        account = await uow.repositories.accounts.get(user_id=cmd.user)
        if cmd.name is not None:
            account.user.name = cmd.name
        if cmd.fullname is not None:
            account.user.fullname = cmd.fullname
        if cmd.email is not None and cmd.email != account.user.email:
            # Don't change the email, but initiate the request event
            account.events.append(events.accounts.EmailChangeRequested(user=account.user.id, email=cmd.email))
        if cmd.password_hash is not None:
            account.user.password_hash = cmd.password_hash
        await uow.commit()

@handlers.command_handler()
async def verify_email(
        cmd: commands.accounts.VerifyEmail,
        uow: AbstractUnitOfWork,
        auth_service: AbstractAuthService
):
    async with uow.get_uow() as uow:
        token_data = auth_service.validate_email_verification_token(cmd.token)

        user_id = token_data['user_id']
        email = token_data['email']

        account = await uow.repositories.accounts.get(user_id=user_id)
        if account is None:
            raise NoResultFoundError

        existing_email: AccountStored = await uow.repositories.accounts.get(email=email)
        if existing_email is not None and existing_email.user.email_verified:
            raise IdentityExistsError("This email address is already verified on another account")

        account.user.email = email
        account.verify_email()

        # now remove allowed emails and establish the ALLOWED_REGISTRATION relationship
        # todo this relationship is not currently used but may be useful in auditing DB usage and admin activities
        async for admin in uow.repositories.accounts.get_all(allowed_email=email):
            admin.remove_email(email)

        await uow.commit()

@handlers.command_handler()
async def login(
        cmd: commands.accounts.Login,
        uow: AbstractUnitOfWork
):
    # todo logic to record login events etc.
    pass
    # raise NotImplementedError

@handlers.command_handler()
async def add_email(
        cmd: commands.accounts.AddEmail,
        uow: AbstractUnitOfWork
):
    async with uow.get_uow() as uow:
        if await uow.repositories.accounts.get(email=cmd.email):
            raise IdentityExistsError("This email is already registered to an account")

        account:AccountStored = await uow.repositories.accounts.get(user_id=cmd.user)
        account.allow_email(cmd.email)
        await uow.commit()

@handlers.command_handler()
async def remove_email(
        cmd: commands.accounts.RemoveEmail,
        uow: AbstractUnitOfWork
):
    async with uow.get_uow() as uow:
        account = await uow.repositories.accounts.get(user_id=cmd.user)
        try:
            account.remove_email(cmd.email)
        except ValueError:
            raise NoResultFoundError("Email not found among those allowed by this account")
        await uow.commit()

@handlers.command_handler()
async def set_ontology_role(
        cmd: commands.accounts.SetOntologyRole,
        uow: AbstractUnitOfWork
):
    async with uow.get_uow() as uow:
        agent = await uow.repositories.accounts.get(user_id=cmd.agent)
        if not agent.user.ontology_role == OntologyRole.ADMIN:
            raise IllegalOperationError("Only OntologyRole.ADMIN can change user ontology role")

        account = await uow.repositories.accounts.get(user_id=cmd.user)
        account.user.ontology_role = OntologyRole[cmd.role]
        await uow.commit()

@handlers.command_handler()
async def request_affiliation(
        cmd: commands.accounts.RequestAffiliation,
        uow: AbstractUnitOfWork
):
    async with uow.get_uow(user_id=cmd.user) as uow:
        organisation = await uow.repositories.organisations.get(team_id=cmd.team)
        organisation.request_affiliation(
            agent_id=cmd.user,
            user_id=cmd.user,
            team_id=cmd.team,
            access=Access(cmd.access),
            heritable=cmd.heritable
        )
        await uow.commit()

@handlers.command_handler()
async def approve_affiliation(
        cmd: commands.accounts.ApproveAffiliation,
        uow: AbstractUnitOfWork
):
    async with uow.get_uow(user_id=cmd.agent) as uow:
        organisation = await uow.repositories.organisations.get(team_id=cmd.team)
        organisation.authorise_affiliation(
            agent_id = cmd.agent,
            team_id = cmd.team,
            user_id = cmd.user,
            access=Access(cmd.access),
            heritable=cmd.heritable
        )
        await uow.commit()

@handlers.command_handler()
async def remove_affiliation(
        cmd: commands.accounts.RemoveAffiliation,
        uow: AbstractUnitOfWork
):
    async with uow.get_uow(user_id=cmd.agent) as uow:
        organisation = await uow.repositories.organisations.get(team_id=cmd.team)
        organisation.remove_affiliation(
            agent_id = cmd.agent,
            team_id = cmd.team,
            user_id = cmd.user,
            access=Access(cmd.access)
        )
        await uow.commit()

@handlers.command_handler()
async def revoke_affiliation(
        cmd: commands.accounts.RevokeAffiliation,
        uow: AbstractUnitOfWork
):
    async with uow.get_uow(user_id=cmd.agent) as uow:
        organisation = await uow.repositories.organisations.get(team_id=cmd.team)
        organisation.revoke_affiliation(
            agent_id = cmd.agent,
            team_id = cmd.team,
            user_id = cmd.user,
            access=Access(cmd.access)
        )
        await uow.commit()