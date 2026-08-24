from ariadne import ObjectType

from typing import List

from breedgraph.domain.model.accounts import (
    AccountOutput,
    UserOutput,
    OntologyRole
)
from breedgraph.domain.model.controls import Access
from breedgraph.custom_exceptions import NoResultFoundError

from breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import (
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

@graphql_query.field("accountsAccount")
@graphql_payload
@require_authentication
async def get_account(_, info) -> AccountOutput:
    user_id = info.context.get('user_id')
    bus = info.context.get('bus')
    async with bus.uow_factory.get_uow() as uow:
        account_stored = await uow.repositories.accounts.get(user_id=user_id)
        if account_stored is None:
            raise NoResultFoundError
        else:
            user_output = UserOutput.from_stored(account_stored.user)
            return AccountOutput(user=user_output, allowed_emails=account_stored.allowed_emails)

@graphql_query.field("accountsUserAccess")
@graphql_payload
@require_authentication
async def get_user_access(_, info) -> dict:
    """Get streamlined access teams for a user"""
    # Use current user if no user provided
    user_id = info.context.get('user_id')
    bus = info.context.get('bus')
    async with bus.views_factory.get_views(user_id=user_id) as views:
        user_ = await views.accounts.get_user()
        if user_ is None:
            raise NoResultFoundError
        else:
            default_write_team_id = user_.default_write_team

    async with bus.uow_factory.get_uow(user_id=user_id) as uow:
        access_teams = uow.controls.access_teams
        # Convert Access enum keys to strings and sets to lists for GraphQL and to ensure order of write teams
        access_teams = {
            access.value.casefold(): list(teams)
            for access, teams in access_teams.items()
        }
        if default_write_team_id in access_teams['write']:
            access_teams['write'].remove(default_write_team_id)
            access_teams['write'].insert(0, default_write_team_id)
        return access_teams

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
