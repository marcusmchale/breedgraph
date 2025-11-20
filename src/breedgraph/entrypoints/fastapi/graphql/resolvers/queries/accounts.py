from ariadne import ObjectType

from typing import List

from src.breedgraph.domain.model.accounts import (
    AccountOutput,
    UserOutput,
    OntologyRole
)
from src.breedgraph.custom_exceptions import NoResultFoundError

from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import (
    update_users_map,
    update_teams_map
)

import logging
logger = logging.getLogger(__name__)

from . import graphql_query
from ..registry import graphql_resolvers
account = ObjectType("Account")
user = ObjectType("User")
user_access = ObjectType("UserAccess")
graphql_resolvers.register_type_resolvers(account, user, user_access)


@graphql_query.field("accountsUsers")
@graphql_payload
@require_authentication
async def get_users(_, info, user: None|int = None) -> List[UserOutput]:
    await update_users_map(info.context, user_ids=[user] if user else None)
    users_map = info.context.get('users_map')
    # then return the list of values
    if user:
        return [users_map[user]]
    else:
        return list(users_map.values())

@graphql_query.field("accountsAccount")
@graphql_payload
@require_authentication
async def get_account(_, info) -> AccountOutput:
    user_id = info.context.get('user_id')
    bus = info.context.get('bus')
    async with bus.uow.get_uow() as uow:
        account_ = await uow.repositories.accounts.get(user_id=user_id)
        if account_ is None:
            raise NoResultFoundError
        else:
            return AccountOutput(user=account_.user, allowed_emails=account_.allowed_emails)

@graphql_query.field("accountsUserAccess")
@graphql_payload
@require_authentication
async def get_user_access(_, info) -> dict:
    """Get streamlined access teams for a user"""
    # Use current user if no user provided
    user_id = info.context.get('user_id')
    bus = info.context.get('bus')
    async with bus.uow.get_uow(user_id=user_id) as uow:
        access_teams = uow.controls.access_teams
        # Convert Access enum keys to strings and sets to lists for GraphQL
        return {
            access.value.casefold(): list(teams)
            for access, teams in access_teams.items()
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
