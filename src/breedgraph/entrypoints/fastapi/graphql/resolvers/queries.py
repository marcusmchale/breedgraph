from itsdangerous import URLSafeTimedSerializer

from src.breedgraph import config

from src.breedgraph import views
from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload
from src.breedgraph.domain.commands.accounts import (
    AddFirstAccount,
    AddAccount,
    Login,
    VerifyEmail,
    AddTeam,
    AddEmail, RemoveEmail
)

from . import graphql_query, graphql_mutation

from typing import List, Optional
from src.breedgraph.domain.model.accounts import (
    AccountStored, UserOutput
)
from src.breedgraph.domain.model.organisations import (
    TeamStored, TeamOutput
)
from src.breedgraph.domain.model.authentication import Token

from src.breedgraph.custom_exceptions import (
    NoResultFoundError,
    IdentityExistsError,
    ProtectedNodeError,
    UnauthorisedOperationError
)

import logging
logger = logging.getLogger(__name__)

@graphql_query.field("get_teams")
@graphql_payload
async def get_teams(_, info) -> List[TeamOutput]:
    account = info.context.get('account')
    if account is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    return [
        TeamOutput(name=team.name, fullname=team.fullname, id=team.id)
        async for team in views.accounts.teams(info.context['bus'].uow, user_id=account.user.id)
    ]
