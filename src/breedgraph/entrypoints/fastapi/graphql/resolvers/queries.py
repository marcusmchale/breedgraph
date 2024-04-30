from itsdangerous import URLSafeTimedSerializer
from ariadne import ObjectType
from src.breedgraph import config

from src.breedgraph import views
from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload

from . import graphql_query, graphql_mutation

from typing import List
from src.breedgraph.domain.model.accounts import (
    AccountStored, AccountOutput,
    Access, Authorisation, Affiliation
)
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

team = ObjectType("Team")  #todo consider renaming to reflect their type
affiliation = ObjectType("Affiliation")

async def inject_teams_map(context):
    if 'teams_map' in context:
        return context['teams_map']

    a = context.get('account')
    if a is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    # insert the team map into the context for building parent/child relationships in the resolver
    teams_map = dict()
    async for t in views.accounts.teams(context['bus'].uow, user=a.user.id):
        teams_map[t.id] = dict(t)
    context['teams_map'] = teams_map
    return teams_map

@graphql_query.field("teams")
@graphql_payload
async def get_teams(_, info, team_id: None|int = None) -> List[dict]:
    teams_map = await inject_teams_map(info.context)
    # then return the list of values
    if team_id is not None:
        return [teams_map[team_id]]
    else:
        return list(teams_map.values())

@team.field("parent")
def resolve_parent(obj, info):
    if obj['parent']:
        return info.context['teams_map'][obj['parent']]

@team.field("children")
def resolve_children(obj, info):
    if obj['children']:
        return [info.context['teams_map'][child] for child in obj['children']]


async def inject_accounts_map(context):
    if 'accounts_map' in context:
        return context['accounts_map']

    a = context.get('account')
    if a is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    accounts_map = dict()

    async for acc in views.accounts.accounts(context['bus'].uow, user=a.user.id):

        accounts_map[acc.user.id] = AccountOutput(user = acc.user, affiliations = acc.affiliations)
        #accounts_map[acc.user.id] = dict()
        #accounts_map[acc.user.id]['user'] = dict(acc.user)
        #accounts_map[acc.user.id]['affiliations'] = [dict(aff) for aff in acc.affiliations]

    # insert the accounts map into the context for building responses in the resolver
    context['accounts_map'] = accounts_map
    return accounts_map

@graphql_query.field("account")
@graphql_payload
async def get_account(_, info) -> List[AccountOutput]:
    a: AccountStored = info.context.get('account')
    await inject_teams_map(info.context)

    if a is None:
        raise UnauthorisedOperationError("Please provide a valid token")
    #
    #return [
    #    {
    #        'user': a.user.to_output(),
    #        'affiliations': a.affiliations
    #    }
    #]
    return [AccountOutput(user=a.user.to_output(), affiliations = a.affiliations)]


@graphql_query.field("accounts")
@graphql_payload
async def get_accounts(_, info, user_id: None|int = None) -> List[AccountOutput]:
    accounts_map = await inject_accounts_map(info.context)
    await inject_teams_map(info.context)
    # then return the list of values
    if user_id:
        return [accounts_map[user_id]]
    else:
        return list(accounts_map.values())

@affiliation.field("team")
def resolve_team(obj, info):

    if obj.team:
        return info.context['teams_map'][obj.team]

#@graphql_query.field("get_affiliations")
#@graphql_payload
#async def get_affiliations(
#        _,
#        info,
#        access: Access,
#        authorisation: Authorisation
#) -> List[Affiliation]:
#    account = info.context.get('account')
#    if account is None:
#        raise UnauthorisedOperationError("Please provide a valid token")
#
#    return [
#        a async for a in views.teams.affiliations(
#            info.context['bus'].uow,
#            user_id=account.user.id,
#            access = Access[access],
#            authorisation= Authorisation[authorisation]
#        )
#    ]

#@graphql_query.field("get_affiliations")
#@graphql_payload
#async def get_affiliations(
#        _,
#        info,
#        access: Access,
#        authorisation: Authorisation
#) -> List[Affiliation]:
#    account = info.context.get('account')
#    if account is None:
#        raise UnauthorisedOperationError("Please provide a valid token")
#    return [
#        a async for a in views.teams.affiliations(
#            info.context['bus'].uow,
#            user_id=account.user.id,
#            access = Access[access],
#            authorisation= Authorisation[authorisation]
#        )
#    ]
#
#