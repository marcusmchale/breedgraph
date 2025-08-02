from ariadne import ObjectType

from typing import List

from src.breedgraph.domain.model.organisations import TeamOutput, Affiliation, Affiliations
from src.breedgraph.domain.model.controls import Access


from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries import graphql_query
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import (
    update_users_map,
    update_teams_map
)

import logging
logger = logging.getLogger(__name__)

team = ObjectType("Team")
affiliations = ObjectType("Affiliations")
affiliation = ObjectType("Affiliation")
user = ObjectType("User")
user_access = ObjectType("UserAccess")

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
    await update_teams_map(info.context, team_ids=[team_id])
    teams_map = info.context.get('teams_map')
    return teams_map.get(team_id, None)

@graphql_query.field("teams")
@graphql_payload
@require_authentication
async def get_teams(_, info, team_ids: List[int]) -> List[TeamOutput]:
    await update_teams_map(info.context, team_ids=team_ids)
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
    await update_users_map(info.context, user_ids=[obj.get('user')])
    return info.context.get('users_map', {}).get(obj.get('user'))


@graphql_query.field("user_access")
@graphql_payload
@require_authentication
async def get_user_access(_, info) -> dict:
    """Get streamlined access teams for a user"""
    # Use current user if no user_id provided
    user_id = info.context.get('user_id')
    bus = info.context.get('bus')
    access_teams = await bus.uow.views.access_teams(user_id)
    # Convert Access enum keys to strings and sets to lists for GraphQL
    return {
        access.value.casefold(): list(team_ids)
        for access, team_ids in access_teams.items()
    }

# Field resolvers for UserAccess type
@user_access.field("read")
async def resolve_read_teams(obj: dict, info):
    team_ids = obj.get('read', [])
    await update_teams_map(info.context, team_ids)
    teams_map = info.context.get('teams_map', {})
    return [teams_map.get(team_id) for team_id in team_ids if teams_map.get(team_id)]

@user_access.field("write")
async def resolve_write_teams(obj: dict, info):
    team_ids = obj.get('write', [])
    await update_teams_map(info.context, team_ids)
    teams_map = info.context.get('teams_map', {})
    return [teams_map.get(team_id) for team_id in team_ids if teams_map.get(team_id)]

@user_access.field("admin")
async def resolve_admin_teams(obj: dict, info):
    team_ids = obj.get('admin', [])
    await update_teams_map(info.context, team_ids)
    teams_map = info.context.get('teams_map', {})
    return [teams_map.get(team_id) for team_id in team_ids if teams_map.get(team_id)]

@user_access.field("curate")
async def resolve_curate_teams(obj: dict, info):
    team_ids = obj.get('curate', [])
    await update_teams_map(info.context, team_ids)
    teams_map = info.context.get('teams_map', {})
    return [teams_map.get(team_id) for team_id in team_ids if teams_map.get(team_id)]
