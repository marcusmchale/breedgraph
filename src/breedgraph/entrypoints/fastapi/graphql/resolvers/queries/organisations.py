from ariadne import ObjectType

from typing import List

from breedgraph.domain.model.organisations import TeamOutput

from breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication

from breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import (
    update_users_map,
    update_teams_map
)

import logging
logger = logging.getLogger(__name__)

from . import graphql_query
from ..registry import graphql_resolvers

team = ObjectType("Team")
affiliations = ObjectType("Affiliations")
affiliation = ObjectType("Affiliation")
user = ObjectType("User")
graphql_resolvers.register_type_resolvers(team, affiliations, affiliation, user)

@graphql_query.field("organisations")
@graphql_payload
@require_authentication
async def get_organisations(_, info) -> List[TeamOutput]:
    await update_teams_map(info.context)
    teams_map = info.context.get('teams_map')
    organisation_roots = info.context.get('organisation_roots')
    return [teams_map.get(i) for i in organisation_roots]

@graphql_query.field("organisationsTeam")
@graphql_payload
@require_authentication
async def get_team(_, info, id: int) -> TeamOutput:
    await update_teams_map(info.context, team_ids=[id])
    teams_map = info.context.get('teams_map')
    return teams_map.get(id, None)

@graphql_query.field("organisationsTeams")
@graphql_payload
@require_authentication
async def get_teams(_, info, ids: List[int]) -> List[TeamOutput]:
    await update_teams_map(info.context, team_ids=ids)
    teams_map = info.context.get('teams_map')
    return [teams_map.get(team_id) for team_id in ids if team_id in teams_map]

@team.field("parent")
def resolve_parent(obj, info):
    return info.context.get('teams_map').get(obj.parent)

@team.field("children")
def resolve_children(obj, info):
    return [info.context.get('teams_map').get(child) for child in obj.children]

@team.field("affiliations")
async def resolve_affiliations(obj, info):
    return obj.affiliations

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
    await update_users_map(info.context, user_ids=[obj.get('user')])
    return info.context.get('users_map', {}).get(obj.get('user'))
