from ariadne import ObjectType

from typing import List

from src.breedgraph.domain.model.organisations import TeamOutput
from src.breedgraph.domain.model.controls import Access

from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload
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
async def get_organisations(_, info) -> List[TeamOutput]:
    await update_teams_map(info.context)
    teams_map = info.context.get('teams_map')
    organisation_roots = info.context.get('organisation_roots')
    return [teams_map.get(i) for i in organisation_roots]

@graphql_query.field("team")
@graphql_payload
async def get_team(_, info, team_id: int) -> TeamOutput:
    await update_teams_map(info.context, team_id=team_id)
    teams_map = info.context.get('teams_map')
    return teams_map.get(team_id, None)

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
        for key, value in obj.get(Access.READ).items()
    ]

@affiliations.field("write")
def resolve_write(obj, info):
    return [
        {'user': key, 'authorisation': value.authorisation, 'heritable': value.heritable}
        for key, value in obj.get(Access.WRITE).items()
    ]

@affiliations.field("curate")
def resolve_curate(obj, info):
    return [
        {'user': key, 'authorisation': value.authorisation, 'heritable': value.heritable}
        for key, value in obj.get(Access.CURATE).items()
    ]
@affiliations.field("admin")
def resolve_admin(obj, info):
    return [
        {'user': key, 'authorisation': value.authorisation, 'heritable': value.heritable}
        for key, value in obj.get(Access.ADMIN).items()
    ]

@affiliation.field("user")
async def resolve_user(obj, info):
    await inject_users_map(info.context)
    return info.context.get('users_map', {}).get(obj.get('user'))
