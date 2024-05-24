from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload
from src.breedgraph.domain.commands.organisations import (
    AddTeam, RemoveTeam,
)
from src.breedgraph.custom_exceptions import UnauthorisedOperationError
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.mutations import graphql_mutation

from typing import Optional

import logging
logger = logging.getLogger(__name__)

@graphql_mutation.field("add_team")
@graphql_payload
async def add_team(
        _,
        info,
        name: str,
        fullname: Optional[str] = None,
        parent: Optional[int] = None
) -> bool:
    account = info.context.get('account')
    if account is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    logger.debug(f"User {account.user.id} adds team: {name}")
    cmd = AddTeam(
        user=account.user.id,
        name=name,
        fullname=fullname,
        parent=parent
    )
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("remove_team")
@graphql_payload
async def remove_team(
        _,
        info,
        team: int
) -> bool:
    account = info.context.get('account')
    if account is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    logger.debug(f"User {account.user.id} removes team: {team}")
    cmd = RemoveTeam(
        user=account.user.id,
        team=team
    )
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("edit_team")
@graphql_payload
async def edit_team(
        _,
        info,
        team: int,
        name: str|None = None,
        fullname: str|None = None
) -> bool:
    account = info.context.get('account')
    if account is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    logger.debug(f"User {account.user.id} edits team: {team}")
    cmd = EditTeam(
        user=account.user.id,
        team=team,
        name=name,
        fullname=fullname
    )
    await info.context['bus'].handle(cmd)
    return True

