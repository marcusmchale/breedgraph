from breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from breedgraph.domain.commands.people import (
    CreatePerson, UpdatePerson, ErasePerson,
    RequestPersonClaim, WithdrawPersonClaim, ApprovePersonClaim, RejectPersonClaim, UnlinkPerson,
    RemoveSelfAsContact, ContactPerson
)
from breedgraph.domain.model.controls import ReadRelease, ControlledModelLabel

import logging
logger = logging.getLogger(__name__)

from . import graphql_mutation

# Person payloads contain personal data, so only IDs and actions are logged

@graphql_mutation.field("peopleCreatePerson")
@graphql_payload
@require_authentication
async def create_person(
        _,
        info,
        person: dict,
        control_team_id: int,
        release: ReadRelease = ReadRelease.PRIVATE
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates a Person controlled by team {control_team_id}")
    optional = {'basis': person['basis']} if person.get('basis') else {}
    cmd = CreatePerson(
        agent_id=user_id,
        write_team=control_team_id,
        release=release or ReadRelease.PRIVATE,
        name=person['name'],
        teams=person.get('team_ids'),
        informed_attestation=person['informed_attestation'],
        **optional
    )
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("peopleUpdatePerson")
@graphql_payload
@require_authentication
async def update_person(_, info, person: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} updates Person {person.get('id')}")
    cmd = UpdatePerson(
        agent_id=user_id,
        person_id=person['id'],
        name=person.get('name'),
        teams=person.get('team_ids'),
        basis=person.get('basis')
    )
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("peopleErasePerson")
@graphql_payload
@require_authentication
async def erase_person(_, info, id: int) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} erases Person {id}")
    await info.context['bus'].handle(ErasePerson(agent_id=user_id, person_id=id))
    return True

@graphql_mutation.field("peopleRequestClaim")
@graphql_payload
@require_authentication
async def request_claim(_, info, person_id: int) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} asks to be linked to Person {person_id}")
    await info.context['bus'].handle(RequestPersonClaim(agent_id=user_id, person_id=person_id))
    return True

@graphql_mutation.field("peopleWithdrawClaim")
@graphql_payload
@require_authentication
async def withdraw_claim(_, info, person_id: int) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} withdraws request to be linked to Person {person_id}")
    await info.context['bus'].handle(WithdrawPersonClaim(agent_id=user_id, person_id=person_id))
    return True

@graphql_mutation.field("peopleApproveClaim")
@graphql_payload
@require_authentication
async def approve_claim(_, info, person_id: int, user_id: int) -> bool:
    agent_id = info.context.get('user_id')
    logger.debug(f"User {agent_id} approves linking user {user_id} to Person {person_id}")
    await info.context['bus'].handle(ApprovePersonClaim(agent_id=agent_id, person_id=person_id, user_id=user_id))
    return True

@graphql_mutation.field("peopleRejectClaim")
@graphql_payload
@require_authentication
async def reject_claim(_, info, person_id: int, user_id: int) -> bool:
    agent_id = info.context.get('user_id')
    logger.debug(f"User {agent_id} rejects linking user {user_id} to Person {person_id}")
    await info.context['bus'].handle(RejectPersonClaim(agent_id=agent_id, person_id=person_id, user_id=user_id))
    return True

@graphql_mutation.field("peopleUnlinkPerson")
@graphql_payload
@require_authentication
async def unlink_person(_, info, person_id: int) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} unlinks Person {person_id}")
    await info.context['bus'].handle(UnlinkPerson(agent_id=user_id, person_id=person_id))
    return True

@graphql_mutation.field("peopleRemoveSelfAsContact")
@graphql_payload
@require_authentication
async def remove_self_as_contact(_, info, entity_label: ControlledModelLabel, entity_id: int) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} removes themselves as a contact of {entity_label.value} {entity_id}")
    await info.context['bus'].handle(RemoveSelfAsContact(agent_id=user_id, entity_label=entity_label, entity_id=entity_id))
    return True

@graphql_mutation.field("peopleContactPerson")
@graphql_payload
@require_authentication
async def contact_person(
        _,
        info,
        person_id: int,
        entity_label: ControlledModelLabel,
        entity_id: int,
        subject: str,
        message: str
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} messages Person {person_id}")
    await info.context['bus'].handle(ContactPerson(
        agent_id=user_id,
        person_id=person_id,
        entity_label=entity_label,
        entity_id=entity_id,
        subject=subject,
        message=message
    ))
    return True
