from breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from breedgraph.domain.commands.people import CreatePerson, UpdatePerson, ErasePerson
from breedgraph.domain.model.controls import ReadRelease

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
