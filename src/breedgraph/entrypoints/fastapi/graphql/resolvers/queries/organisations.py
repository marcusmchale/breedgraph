from ariadne import ObjectType

from typing import List
#from src.breedgraph.domain.model.organisations import TeamOutput
from src.breedgraph.domain.model.organisations import Organisation, TeamOutput

from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries import graphql_query
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import (
    inject_users_map,
    inject_teams_map
)

import logging
logger = logging.getLogger(__name__)

team = ObjectType("Team")
affiliations = ObjectType("Affiliations")
#affiliation = ObjectType("Affiliation")

@graphql_query.field("organisations")
@graphql_payload
async def get_organisations(_, info) -> List[TeamOutput]:
    await inject_teams_map(info.context)
    teams_map = info.context.get('teams_map')
    organisation_roots = info.context.get('organisation_roots')
    return [teams_map.get(i) for i in organisation_roots]

@graphql_query.field("team")
@graphql_payload
async def get_team(_, info, team_id: int) -> List[TeamOutput]:
    await inject_teams_map(info.context)
    teams_map = info.context.get('teams_map')
    return teams_map.get(team_id, None)

@team.field("parent")
def resolve_parent(obj, info):
    return info.context.get('teams_map').get(obj.parent)

@team.field("children")
def resolve_children(obj, info):
    return [info.context.get('teams_map').get(child) for child in obj.children]

@team.field("affiliations")
async def resolve_affiliations(obj, info):
    await inject_users_map(info.context)
    return [info.context.get('users_map').get(i) for i in obj.readers]

@affiliations.field("read")
def resolve_read(obj, info):
    raise NotImplementedError

