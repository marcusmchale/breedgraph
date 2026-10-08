from breedgraph.domain import commands
from breedgraph.domain.events.people import PersonErased, PersonClaimRequested, PersonLinked
from breedgraph.domain.model.controls import Access
from breedgraph.domain.model.people import PersonInput, PersonStored, normalise_orcid
from breedgraph.custom_exceptions import (
    IllegalOperationError,
    NoResultFoundError,
    UnauthorisedOperationError
)

from breedgraph.service_layer.infrastructure import (
    AbstractUnitOfWorkFactory, AbstractUnitHolder, AbstractNotifications, AbstractStateStore, AbstractOrcidService
)
import secrets
from breedgraph.service_layer.infrastructure.notifications import email_templates
from breedgraph.domain.model.controls import ControlledModelLabel
from breedgraph import config

from ..registry import handlers

from typing import Iterable

import logging
logger = logging.getLogger(__name__)


async def _verify_teams(uow: AbstractUnitHolder, team_ids: Iterable[int] | None) -> None:
    team_ids = set(team_ids or [])
    if not team_ids:
        return
    found = set()
    async for organisation in uow.repositories.organisations.get_all(team_ids=team_ids):
        found.update(team.id for team in organisation.teams)
    missing = team_ids - found
    if missing:
        raise NoResultFoundError(f"Teams not found: {sorted(missing)}")


async def _get_person(uow: AbstractUnitHolder, person_id: int) -> PersonStored:
    person = await uow.repositories.people.get(person_id=person_id)
    if person is None:
        raise NoResultFoundError(f"Person {person_id} not found")
    return person


@handlers.command_handler()
async def create_person(
        cmd: commands.people.CreatePerson,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id, write_team=cmd.write_team, release=cmd.release) as uow:
        # The organisation of the write team is the data controller for the Person
        organisation = await uow.repositories.organisations.get(team_id=cmd.write_team)
        if organisation is None or organisation.legal_entity is None:
            raise IllegalOperationError(
                "Recording a Person requires the write team's organisation to have declared its legal entity"
            )
        await _verify_teams(uow, cmd.teams)

        await uow.repositories.people.create(PersonInput(
            name=cmd.name,
            teams=list(cmd.teams or []),
            basis=cmd.basis,
            informed_attestation=cmd.informed_attestation
        ))
        await uow.commit()


@handlers.command_handler()
async def update_person(
        cmd: commands.people.UpdatePerson,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        person = await _get_person(uow, cmd.person_id)
        if person.erased:
            raise IllegalOperationError("An erased Person cannot be changed")

        # The linked user can change their name, other changes need curate access to the record
        controller = await uow.controls.get_controller(person.label, person.id)
        is_curator = controller.has_access(Access.CURATE, access_teams=uow.controls.access_teams[Access.CURATE])
        if not is_curator and (cmd.teams is not None or cmd.basis is not None):
            raise UnauthorisedOperationError("Changing the teams or basis of a Person requires curate access")

        if cmd.name is not None:
            name = cmd.name.strip()
            if not name:
                raise IllegalOperationError("A Person requires a name")
            person.name = name
        if cmd.teams is not None:
            await _verify_teams(uow, cmd.teams)
            person.teams = list(cmd.teams)
        if cmd.basis is not None:
            person.basis = cmd.basis
        await uow.commit()


@handlers.command_handler()
async def erase_person(
        cmd: commands.people.ErasePerson,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        person = await _get_person(uow, cmd.person_id)
        controller = await uow.controls.get_controller(person.label, person.id)
        person.erase(
            agent_id=cmd.agent_id,
            controller=controller,
            admin_teams=uow.controls.access_teams[Access.ADMIN]
        )
        person.events.append(PersonErased(person_id=person.id, erased_at=person.erased_at))
        await uow.commit()


async def _require_unlinked_user(uow: AbstractUnitHolder, user_id: int) -> None:
    """Each account can be linked to one Person"""
    if await uow.repositories.people.get(user_id=user_id) is not None:
        raise IllegalOperationError("This account is already linked to a Person")


async def _admin_context(uow: AbstractUnitHolder, person: PersonStored):
    controller = await uow.controls.get_controller(person.label, person.id)
    return controller, uow.controls.access_teams[Access.ADMIN]


@handlers.command_handler()
async def request_person_claim(
        cmd: commands.people.RequestPersonClaim,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        await _require_unlinked_user(uow, cmd.agent_id)
        person = await _get_person(uow, cmd.person_id)
        person.request_claim(cmd.agent_id)
        person.events.append(PersonClaimRequested(person_id=person.id, user_id=cmd.agent_id))
        await uow.commit()


@handlers.command_handler()
async def withdraw_person_claim(
        cmd: commands.people.WithdrawPersonClaim,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        person = await _get_person(uow, cmd.person_id)
        person.withdraw_claim(cmd.agent_id)
        await uow.commit()


@handlers.command_handler()
async def approve_person_claim(
        cmd: commands.people.ApprovePersonClaim,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        await _require_unlinked_user(uow, cmd.user_id)
        person = await _get_person(uow, cmd.person_id)
        controller, admin_teams = await _admin_context(uow, person)
        person.approve_claim(cmd.agent_id, cmd.user_id, controller, admin_teams)
        person.events.append(PersonLinked(person_id=person.id, user_id=cmd.user_id))
        await uow.commit()


@handlers.command_handler()
async def reject_person_claim(
        cmd: commands.people.RejectPersonClaim,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        person = await _get_person(uow, cmd.person_id)
        controller, admin_teams = await _admin_context(uow, person)
        person.reject_claim(cmd.agent_id, cmd.user_id, controller, admin_teams)
        await uow.commit()


@handlers.command_handler()
async def unlink_person(
        cmd: commands.people.UnlinkPerson,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        person = await _get_person(uow, cmd.person_id)
        controller, admin_teams = await _admin_context(uow, person)
        person.unlink(cmd.agent_id, controller, admin_teams)
        await uow.commit()


@handlers.command_handler()
async def remove_self_as_contact(
        cmd: commands.people.RemoveSelfAsContact,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        person = await uow.repositories.people.get(user_id=cmd.agent_id)
        if person is None:
            raise NoResultFoundError("Your account is not linked to a Person")
        if not await uow.repositories.people.remove_contact(person.id, cmd.entity_label, cmd.entity_id):
            raise NoResultFoundError(f"You are not a contact of {cmd.entity_label.value} {cmd.entity_id}")
        await uow.commit()


async def _entity_name(uow: AbstractUnitHolder, label: ControlledModelLabel, entity_id: int) -> str:
    if label is ControlledModelLabel.PROGRAM:
        program = await uow.repositories.programs.get(program_id=entity_id)
        return f"the program {program.name}"
    program = await uow.repositories.programs.get(trial_id=entity_id)
    return f"the trial {program.get_trial(entity_id).name}"


@handlers.command_handler()
async def contact_person(
        cmd: commands.people.ContactPerson,
        uow_factory: AbstractUnitOfWorkFactory,
        state_store: AbstractStateStore,
        notifications: AbstractNotifications
):
    """
    Send a message to a contact of a Program or Trial the sender can read.
    The recipient's email address is never revealed; the sender's is given as reply-to.
    """
    subject = ' '.join((cmd.subject or '').split())
    message = (cmd.message or '').strip()
    if not subject or not message:
        raise IllegalOperationError("A subject and message are required")
    if len(subject) > config.MESSAGE_SUBJECT_MAX_LENGTH or len(message) > config.MESSAGE_MAX_LENGTH:
        raise IllegalOperationError(
            f"Subjects are limited to {config.MESSAGE_SUBJECT_MAX_LENGTH} and messages to {config.MESSAGE_MAX_LENGTH} characters"
        )
    if cmd.entity_label not in (ControlledModelLabel.PROGRAM, ControlledModelLabel.TRIAL):
        raise IllegalOperationError("Contacts are listed on Programs and Trials")
    sent = await state_store.increment_rate_counter(f"contact:{cmd.agent_id}", window_seconds=3600)
    if sent > config.MESSAGE_RATE_LIMIT_PER_HOUR:
        raise IllegalOperationError("You have reached the limit of messages per hour, please try again later")

    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        if (cmd.entity_label, cmd.entity_id) not in await uow.repositories.people.get_contact_entities(cmd.person_id):
            raise NoResultFoundError(f"Person {cmd.person_id} is not a contact of {cmd.entity_label.value} {cmd.entity_id}")
        controller = await uow.controls.get_controller(cmd.entity_label, cmd.entity_id)
        if not controller.has_access(Access.READ, cmd.agent_id, uow.controls.access_teams[Access.READ]):
            raise NoResultFoundError(f"{cmd.entity_label.value} {cmd.entity_id} not found")
        recipient_id = await uow.repositories.people.get_linked_user(cmd.person_id)
        if recipient_id is None:
            raise IllegalOperationError(f"Person {cmd.person_id} is not linked to an account, so cannot be messaged")
        sender = await uow.repositories.accounts.get(user_id=cmd.agent_id)
        recipient = await uow.repositories.accounts.get(user_id=recipient_id)
        about = await _entity_name(uow, cmd.entity_label, cmd.entity_id)

    await notifications.send([recipient.user], email_templates.ContactMessage(
        sender=sender.user,
        sender_email=sender.user.email,
        about=about,
        subject=subject,
        message=message
    ))
    logger.info(f"User {cmd.agent_id} messaged Person {cmd.person_id} about {cmd.entity_label.value} {cmd.entity_id}")


async def _get_own_person(uow: AbstractUnitHolder, user_id: int) -> PersonStored:
    person = await uow.repositories.people.get(user_id=user_id)
    if person is None:
        raise NoResultFoundError("Your account is not linked to a Person")
    return person


@handlers.command_handler()
async def start_orcid_link(
        cmd: commands.people.StartOrcidLink,
        uow_factory: AbstractUnitOfWorkFactory,
        state_store: AbstractStateStore,
        orcid_service: AbstractOrcidService
) -> str:
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        await _get_own_person(uow, cmd.agent_id)
    state = secrets.token_urlsafe(32)
    url = orcid_service.authorization_url(state)
    await state_store.store_oauth_state(state, cmd.agent_id, expires_seconds=config.ORCID_STATE_EXPIRES_SECONDS)
    return url


@handlers.command_handler()
async def complete_orcid_link(
        cmd: commands.people.CompleteOrcidLink,
        uow_factory: AbstractUnitOfWorkFactory,
        state_store: AbstractStateStore,
        orcid_service: AbstractOrcidService
):
    # The state is single use, and must have been issued to the same user
    if await state_store.pop_oauth_state(cmd.state) != cmd.agent_id:
        raise UnauthorisedOperationError("This ORCID sign-in was not started by you or has expired, please try again")
    orcid = normalise_orcid(await orcid_service.verified_orcid(cmd.code))
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        person = await _get_own_person(uow, cmd.agent_id)
        if await uow.repositories.people.orcid_in_use(orcid, person.id):
            raise IllegalOperationError("This ORCID iD is already linked to another Person")
        person.set_orcid(cmd.agent_id, orcid)
        await uow.commit()
    logger.info(f"User {cmd.agent_id} linked an ORCID iD to Person {person.id}")


@handlers.command_handler()
async def remove_orcid(
        cmd: commands.people.RemoveOrcid,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        person = await _get_own_person(uow, cmd.agent_id)
        person.remove_orcid(cmd.agent_id)
        await uow.commit()
