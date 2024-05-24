from ariadne import ObjectType

from typing import List
from src.breedgraph.domain.model.accounts import (
    AccountStored, AccountOutput,
    Access, Authorisation,
    UserOutput
)

from src.breedgraph.custom_exceptions import UnauthorisedOperationError

from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import (
    inject_users_map,
    inject_teams_map
)
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries import graphql_query


import logging
logger = logging.getLogger(__name__)

account = ObjectType("Account")

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

