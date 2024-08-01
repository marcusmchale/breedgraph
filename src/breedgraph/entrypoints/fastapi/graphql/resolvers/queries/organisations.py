from ariadne import ObjectType

from typing import List
#from src.breedgraph.domain.model.organisations import TeamOutput
from src.breedgraph.domain.model.organisations import Organisation, TeamOutput

from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries import graphql_query
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import (
    inject_users_map, inject_teams_map
)

import logging
logger = logging.getLogger(__name__)

team = ObjectType("Team")

@graphql_query.field("teams")
@graphql_payload
async def get_teams(_, info, team_id: None|int = None) -> List[TeamOutput]:
    await inject_teams_map(info.context)
    await inject_users_map(info.context)

    teams_map = info.context.get('teams_map')
    if team_id is not None:
        return [teams_map[team_id]]
    else:
        return list(teams_map.values())

@team.field("parent")
def resolve_parent(obj, info):
    return info.context.get('teams_map').get(obj.parent)

@team.field("children")
def resolve_children(obj, info):
    return [info.context.get('teams_map').get(child) for child in obj.children]

@team.field("readers")
def resolve_readers(obj, info):
    return [info.context.get('users_map').get(i) for i in obj.readers]

@team.field("writers")
def resolve_writers(obj, info):
    return [info.context.get('users_map').get(i) for i in obj.writers]

@team.field("admins")
def resolve_admins(obj, info):
    return [info.context.get('users_map').get(i) for i in obj.admins]

@team.field("read_requests")
def resolve_read_requests(obj, info):
    return [info.context.get('users_map').get(i) for i in obj.read_requests]

@team.field("write_requests")
def resolve_writers(obj, info):
    return [info.context.get('users_map').get(i) for i in obj.write_requests]

@team.field("admin_requests")
def resolve_admins(obj, info):
    return [info.context.get('users_map').get(i) for i in obj.admin_requests]