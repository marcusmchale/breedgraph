from ariadne import ObjectType

from typing import List

from src.breedgraph.domain.model.organisations import TeamOutput, Affiliation, Affiliations
from src.breedgraph.domain.model.controls import Access


from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries import graphql_query
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import (
    inject_users_map,
    update_teams_map
)

import logging
logger = logging.getLogger(__name__)

team = ObjectType("Team")
affiliations = ObjectType("Affiliations")
affiliation = ObjectType("Affiliation")
user = ObjectType("User")

@graphql_query.field("organisations")
@graphql_payload
@require_authentication
async def get_organisations(_, info) -> List[TeamOutput]:
    await update_teams_map(info.context)
    teams_map = info.context.get('teams_map')
    organisation_roots = info.context.get('organisation_roots')
    return [teams_map.get(i) for i in organisation_roots]

@graphql_query.field("team")
@graphql_payload
@require_authentication
async def get_team(_, info, team_id: int) -> TeamOutput:
    await update_teams_map(info.context, team_id=team_id)
    teams_map = info.context.get('teams_map')
    return teams_map.get(team_id, None)

@graphql_query.field("teams")
@graphql_payload
@require_authentication
async def get_teams(_, info, team_ids: List[int]) -> List[TeamOutput]:
    for team_id in team_ids:
        await update_teams_map(info.context, team_id=team_id)
    teams_map = info.context.get('teams_map')
    return [teams_map.get(team_id) for team_id in team_ids if team_id in teams_map]

@graphql_query.field("inherited_affiliations")
@graphql_payload
@require_authentication
async def get_inherited_affiliations(_, info, team_id) -> Affiliations:
    user_id = info.context.get('user_id')
    bus = info.context.get('bus')
    async with bus.uow.get_repositories(user_id=user_id) as uow:
        organisation = await uow.organisations.get(team_id=team_id)
        if organisation is not None:
            return organisation.get_inherited_affiliations(team_id)
        else:
            return Affiliations()

@team.field("parent")
def resolve_parent(obj, info):
    return info.context.get('teams_map').get(obj.parent)

@team.field("children")
def resolve_children(obj, info):
    return [info.context.get('teams_map').get(child) for child in obj.children]

@affiliations.field("read")
def resolve_read(obj, info):
    return [
        {'user': key, 'authorisation': value.authorisation, 'heritable': value.heritable}
        for key, value in obj.read.items()
    ]

@affiliations.field("write")
def resolve_write(obj, info):
    return [
        {'user': key, 'authorisation': value.authorisation, 'heritable': value.heritable}
        for key, value in obj.write.items()
    ]

@affiliations.field("curate")
def resolve_curate(obj, info):
    return [
        {'user': key, 'authorisation': value.authorisation, 'heritable': value.heritable}
        for key, value in obj.curate.items()
    ]
@affiliations.field("admin")
def resolve_admin(obj, info):
    return [
        {'user': key, 'authorisation': value.authorisation, 'heritable': value.heritable}
        for key, value in obj.admin.items()
    ]

@affiliation.field("user")
async def resolve_user(obj, info):
    await inject_users_map(info.context)
    return info.context.get('users_map', {}).get(obj.get('user'))
