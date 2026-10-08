from ariadne import ObjectType, EnumType

from typing import List

from breedgraph.custom_exceptions import NoResultFoundError
from breedgraph.domain.model.people import PersonOutput, LawfulBasis
from breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import (
    update_people_map,
    update_teams_map,
    update_users_map
)

import logging
logger = logging.getLogger(__name__)

from . import graphql_query
from ..registry import graphql_resolvers

person = ObjectType("Person")
graphql_resolvers.register_type_resolvers(person)
graphql_resolvers.register_enums(EnumType("LawfulBasis", LawfulBasis))


@graphql_query.field("people")
@graphql_payload
@require_authentication
async def get_people(_, info, name: str | None = None) -> List[PersonOutput]:
    user_id = info.context.get('user_id')
    bus = info.context.get('bus')
    async with bus.uow_factory.get_uow(user_id=user_id) as uow:
        people = uow.repositories.people.get_all(name=name) if name else uow.repositories.people.get_all()
        return [p.to_output() async for p in people]

@graphql_query.field("peoplePeople")
@graphql_payload
@require_authentication
async def get_people_by_ids(_, info, ids: List[int]) -> List[PersonOutput]:
    await update_people_map(info.context, person_ids=ids)
    people_map = info.context.get('people_map')
    return [people_map[person_id] for person_id in ids if person_id in people_map]

@graphql_query.field("peoplePerson")
@graphql_payload
@require_authentication
async def get_person(_, info, id: int) -> PersonOutput:
    await update_people_map(info.context, person_ids=[id])
    person_output = info.context.get('people_map').get(id)
    if person_output is None:
        raise NoResultFoundError(f"Person {id} not found")
    return person_output

@person.field("teams")
async def resolve_teams(obj: PersonOutput, info):
    await update_teams_map(info.context, team_ids=obj.teams)
    teams_map = info.context.get('teams_map', {})
    return [teams_map[team_id] for team_id in obj.teams if team_id in teams_map]

async def _resolve_user(info, user_id: int | None):
    if user_id is None:
        return None
    await update_users_map(info.context, user_ids=[user_id])
    return info.context.get('users_map', {}).get(user_id)

@person.field("linkedUser")
async def resolve_linked_user(obj: PersonOutput, info):
    return await _resolve_user(info, obj.user)

@person.field("recordedBy")
async def resolve_recorded_by(obj: PersonOutput, info):
    return await _resolve_user(info, obj.recorded_by)

@person.field("erased")
def resolve_erased(obj: PersonOutput, info) -> bool:
    return obj.erased_at is not None

@person.field("restricted")
def resolve_restricted(obj: PersonOutput, info) -> bool:
    # Readers always see a name unless the Person is erased, see PersonStored.redacted
    return obj.name is None and obj.erased_at is None
