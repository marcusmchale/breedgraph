from breedgraph.domain import commands, events
from breedgraph.domain.model.accounts import UserInput, AccountInput, AccountStored, OntologyRole
from breedgraph.domain.model.organisations import Authorisation, Affiliation
from breedgraph.domain.model.invitations import InvitationInput, TeamInvitation
from breedgraph.domain.model.controls import Access, ControlledModelLabel
from breedgraph import config


from breedgraph.service_layer.infrastructure import (
    AbstractUnitOfWorkFactory,
    AbstractAuthService
)


from breedgraph.custom_exceptions import (
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
        uow_factory: AbstractUnitOfWorkFactory,
        auth_service: AbstractAuthService
):
    # Unredacted, to check the inviter still administers the teams offered
    async with uow_factory.get_uow(redacted=False) as uow:
        invitation = None
        if await uow.constraints.accounts_exist():
            # Registration requires an invitation to the email address used
            if not cmd.invitation_token:
                raise UnauthorisedOperationError("Please contact an existing user to be invited")
            token_data = auth_service.validate_invitation_token(cmd.invitation_token)
            invitation = await uow.repositories.invitations.get(invitation_id=token_data['invitation_id'])
            if invitation is None or invitation.is_expired():
                raise UnauthorisedOperationError("This invitation is no longer valid, please ask to be invited again")
            if not invitation.matches_email(cmd.email):
                raise UnauthorisedOperationError("Please register with the email address the invitation was sent to")
            accepted_teams = invitation.accepted_teams(cmd.accept_team_ids)
            ontology_role = OntologyRole.CONTRIBUTOR
        else:
            # first user to register is the first Ontology Admin
            # and is responsible for elevating other users to ADMIN/EDITOR privilege.
            ontology_role = OntologyRole.ADMIN

        # Check for accounts with same email but not verified
        existing_email = await uow.repositories.accounts.get(email=cmd.email)
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
        existing_name = await uow.repositories.accounts.get(name=cmd.name)
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
        account = await uow.repositories.accounts.create(account)

        if invitation is not None:
            for team in accepted_teams:
                await _grant_invited_affiliation(uow, invitation.invited_by, account.user.id, team)
            # The invitation, with the email address, is not kept once accepted
            await uow.repositories.invitations.remove(invitation)
        await uow.commit()


async def _grant_invited_affiliation(uow, inviter_id: int, user_id: int, team: TeamInvitation):
    organisation = await uow.repositories.organisations.get(team_id=team.team_id)
    if organisation is None or inviter_id not in organisation.get_affiliates(team.team_id, access=Access.ADMIN):
        raise IllegalOperationError(
            f"Team {team.team_id} offered with this invitation is no longer administered by the inviter, "
            f"please register without it"
        )
    affiliations = organisation.get_team(team.team_id).affiliations
    affiliations.set_by_access(team.access, user_id, Affiliation(authorisation=Authorisation.AUTHORISED, heritable=False))
    # As for approved requests, curate access includes read access
    if team.access is Access.CURATE:
        affiliations.set_by_access(Access.READ, user_id, Affiliation(authorisation=Authorisation.AUTHORISED, heritable=False))

@handlers.command_handler()
async def edit_user(
        cmd: commands.accounts.UpdateUser,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow() as uow:
        account = await uow.repositories.accounts.get(user_id=cmd.user_id)
        if account is None:
            raise NoResultFoundError(f"Account not found with user id {cmd.user_id}")
        if cmd.name is not None:
            account.user.name = cmd.name
        if cmd.fullname is not None:
            account.user.fullname = cmd.fullname
        if cmd.email != account.user.email:
            if cmd.email is not None:
                # Initiate the change email requested event
                account.events.append(events.accounts.EmailChangeRequested(user_id=account.user.id, email=cmd.email))
        if cmd.password_hash is not None:
            account.user.password_hash = cmd.password_hash
        await uow.commit()

@handlers.command_handler()
async def verify_email(
        cmd: commands.accounts.VerifyEmail,
        uow_factory: AbstractUnitOfWorkFactory,
        auth_service: AbstractAuthService
):
    async with uow_factory.get_uow() as uow:
        token_data = auth_service.validate_email_verification_token(cmd.token)

        user_id = token_data['user_id']
        email = token_data['email']

        account = await uow.repositories.accounts.get(user_id=user_id)
        if account is None:
            raise NoResultFoundError(f"Account not found with user id {cmd.user_id}")

        existing_email= await uow.repositories.accounts.get(email=email)
        if existing_email is not None and existing_email.user.email_verified:
            if account == existing_email:
                raise IllegalOperationError("Email address is already verified!")
            else:
                raise IdentityExistsError("This email address is already verified on another account")

        account.user.email = email
        account.verify_email()
        await uow.commit()

@handlers.command_handler()
async def login(
        cmd: commands.accounts.Login,
        uow_factory: AbstractUnitOfWorkFactory
):
    # todo logic to record login events etc.
    pass
    # raise NotImplementedError

@handlers.command_handler()
async def invite_user(
        cmd: commands.accounts.InviteUser,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        existing = await uow.repositories.accounts.get(email=cmd.email)
        if existing is not None and existing.user.email_verified:
            raise IdentityExistsError("This email address is already registered")
        async for pending in uow.repositories.invitations.get_all(invited_by=cmd.agent_id, email=cmd.email):
            raise IdentityExistsError(f"You have already invited this email address, resend invitation {pending.id} instead")

        invitation = InvitationInput(
            email=cmd.email,
            invited_by=cmd.agent_id,
            teams=[TeamInvitation(team_id=team.team_id, access=team.access) for team in cmd.teams or []],
            person_id=cmd.person_id
        )
        admin_teams = uow.controls.access_teams[Access.ADMIN]
        invitation.check_inviter(admin_teams)
        if cmd.person_id is not None:
            person = await uow.repositories.people.get(person_id=cmd.person_id)
            if person is None or person.erased:
                raise NoResultFoundError(f"Person {cmd.person_id} not found")
            controller = await uow.controls.get_controller(ControlledModelLabel.PERSON, cmd.person_id)
            if not controller.has_access(Access.ADMIN, access_teams=admin_teams):
                raise UnauthorisedOperationError("A Person can only be offered by admins of its controlling teams")

        stored = await uow.repositories.invitations.create(invitation)
        stored.events.append(events.accounts.InvitationIssued(invitation_id=stored.id))
        await uow.commit()


async def _get_own_invitation(uow, agent_id: int, invitation_id: int):
    invitation = await uow.repositories.invitations.get(invitation_id=invitation_id)
    if invitation is None or invitation.invited_by != agent_id:
        raise NoResultFoundError(f"Invitation {invitation_id} not found among your invitations")
    return invitation


@handlers.command_handler()
async def cancel_invitation(
        cmd: commands.accounts.CancelInvitation,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        invitation = await _get_own_invitation(uow, cmd.agent_id, cmd.invitation_id)
        await uow.repositories.invitations.remove(invitation)
        await uow.commit()


@handlers.command_handler()
async def resend_invitation(
        cmd: commands.accounts.ResendInvitation,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        invitation = await _get_own_invitation(uow, cmd.agent_id, cmd.invitation_id)
        invitation.extend(days=config.INVITATION_EXPIRY_DAYS)
        invitation.events.append(events.accounts.InvitationIssued(invitation_id=invitation.id))
        await uow.commit()


@handlers.command_handler()
async def remove_expired_invitations(
        cmd: commands.accounts.RemoveExpiredInvitations,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow() as uow:
        removed = await uow.repositories.invitations.remove_expired()
        await uow.commit()
    logger.info(f"Removed {removed} expired invitations")

@handlers.command_handler()
async def request_ontology_role(
        cmd: commands.accounts.RequestOntologyRole,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.user_id) as uow:
        account = await uow.repositories.accounts.get(user_id=cmd.user_id)
        if account is None:
            raise NoResultFoundError(f"Account not found with user id {cmd.user_id}")
        account.user.ontology_role_requested = OntologyRole(cmd.ontology_role)
        await uow.commit()

@handlers.command_handler()
async def set_ontology_role(
        cmd: commands.accounts.SetOntologyRole,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        # first just check that the user is an admin
        if not await uow.constraints.is_ontology_admin():
            raise UnauthorisedOperationError("Only ontology admins can change roles")

        account = await uow.repositories.accounts.get(user_id=cmd.user_id)
        if account is None:
            raise NoResultFoundError(f"Account not found with user id {cmd.user_id}")
        if account.user.ontology_role == OntologyRole.ADMIN:
            if not account.user.id == cmd.agent_id:
                raise UnauthorisedOperationError('Admins may only change their own role')
            if cmd.ontology_role != OntologyRole.ADMIN and await uow.constraints.is_last_ontology_admin():
                raise IllegalOperationError(
                    "This would result in no ontology admins, please select another admin before retiring!"
                )
        account.user.ontology_role = OntologyRole(cmd.ontology_role)
        await uow.commit()

@handlers.command_handler()
async def set_write_team(
        cmd: commands.accounts.SetWriteTeam,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.user_id) as uow:
        account = await uow.repositories.accounts.get(user_id=cmd.user_id)
        if account is None:
            raise NoResultFoundError(f"Account not found with user id {cmd.user_id}")

        account.user.default_write_team = cmd.team_id
        await uow.commit()

@handlers.command_handler()
async def request_affiliation(
        cmd: commands.accounts.RequestAffiliation,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.user_id) as uow:
        organisation = await uow.repositories.organisations.get(team_id=cmd.team_id)
        if organisation is None:
            raise NoResultFoundError(f"Organisation not found with team id {cmd.team_id}")
        organisation.request_affiliation(
            agent_id=cmd.user_id,
            user_id=cmd.user_id,
            team_id=cmd.team_id,
            access=cmd.access,
            heritable=cmd.heritable
        )
        await uow.commit()

@handlers.command_handler()
async def approve_affiliation(
        cmd: commands.accounts.ApproveAffiliation,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        organisation = await uow.repositories.organisations.get(team_id=cmd.team_id)
        if organisation is None:
            raise NoResultFoundError(f"Organisation not found with team id {cmd.team_id}")

        organisation.authorise_affiliation(
            agent_id = cmd.agent_id,
            team_id = cmd.team_id,
            user_id = cmd.user_id,
            access=cmd.access,
            heritable=cmd.heritable
        )
        await uow.commit()

@handlers.command_handler()
async def remove_affiliation(
        cmd: commands.accounts.RemoveAffiliation,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        organisation = await uow.repositories.organisations.get(team_id=cmd.team_id)
        if organisation is None:
            raise NoResultFoundError(f"Organisation not found with team id {cmd.team_id}")
        organisation.remove_affiliation(
            agent_id = cmd.agent_id,
            team_id = cmd.team_id,
            user_id = cmd.user_id,
            access=cmd.access
        )
        await uow.commit()

@handlers.command_handler()
async def revoke_affiliation(
        cmd: commands.accounts.RevokeAffiliation,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        organisation = await uow.repositories.organisations.get(team_id=cmd.team_id)
        if organisation is None:
            raise NoResultFoundError(f"Organisation not found with team id {cmd.team_id}")
        organisation.revoke_affiliation(
            agent_id = cmd.agent_id,
            team_id = cmd.team_id,
            user_id = cmd.user_id,
            access=cmd.access
        )
        await uow.commit()