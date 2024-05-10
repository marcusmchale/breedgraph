from itsdangerous import URLSafeTimedSerializer
from ariadne import ObjectType
from src.breedgraph import config

from src.breedgraph import views
from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload

from . import graphql_query, graphql_mutation

from typing import List
from src.breedgraph.domain.model.accounts import (
    AccountStored, AccountOutput,
    Affiliation, Access, Authorisation,
    UserStored, UserOutput
)
from src.breedgraph.domain.model.locations import Country

from src.breedgraph.domain.model.organisations import (
    TeamOutput
)

from src.breedgraph.custom_exceptions import (
    NoResultFoundError,
    IdentityExistsError,
    ProtectedNodeError,
    UnauthorisedOperationError
)

import logging
logger = logging.getLogger(__name__)

team = ObjectType("Team")  #todo consider renaming to reflect their graphql type, e.g. gql_team
account = ObjectType("Account")

async def inject_teams_map(context):
    if 'teams_map' in context:
        return

    a = context.get('account')
    if a is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    # insert the team map into the context for building parent/child relationships in the resolver
    teams_map = dict()
    async for t in views.accounts.teams(context['bus'].uow, user=a.user.id):
        teams_map[t.id] = t
    context['teams_map'] = teams_map

async def inject_users_map(context):
    if 'users_map' in context:
        return

    a = context.get('account')
    if a is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    users_map = dict()
    async for user in views.accounts.users(context['bus'].uow, user=a.user.id):
        users_map[user.id] = user

    # insert the accounts map into the context for building responses in the resolver
    context['users_map'] = users_map

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

@graphql_query.field("users")
@graphql_payload
async def get_users(_, info, user_id: None|int = None) -> List[UserOutput]:
    await inject_users_map(info.context)
    users_map = info.context.get('users_map')
    # then return the list of values
    if user_id:
        return [users_map[user_id]]
    else:
        return list(users_map.values())

@graphql_query.field("account")
@graphql_payload
async def get_account(_, info) -> AccountOutput:
    acc: AccountStored = info.context.get('account')
    if acc is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    reads, writes, admins = list(), list(), list()
    for aff in acc.affiliations:
        if aff.authorisation != Authorisation.AUTHORISED:
            continue

        if aff.access == Access.READ:
            reads.append(aff.team)
        elif aff.access == Access.WRITE:
            writes.append(aff.team)
        elif aff.access == Access.ADMIN:
            admins.append(aff.team)

    await inject_teams_map(info.context)
    return AccountOutput(user=UserOutput(**dict(acc.user)), reads=reads, writes=writes, admins=admins)

@account.field("reads")
def resolve_reads(obj, info):
    return [info.context.get('teams_map').get(i) for i in obj.reads]

@account.field("writes")
def resolve_writes(obj, info):
    return [info.context.get('teams_map').get(i) for i in obj.writes]

@account.field("admins")
def resolve_writes(obj, info):
    return [info.context.get('teams_map').get(i) for i in obj.admins]

@graphql_query.field("countries")
@graphql_payload
async def get_countries(_, info) -> List[Country]:
    bus = info.context.get('bus')
    return [c async for c in views.locations.countries(bus.read_model)]
