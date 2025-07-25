from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from src.breedgraph.domain.commands.organisations import (
    AddTeam, RemoveTeam, UpdateTeam
)
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.mutations import graphql_mutation

from typing import Optional

import logging
logger = logging.getLogger(__name__)

@graphql_mutation.field("add_team")
@graphql_payload
@require_authentication
async def add_team(
        _,
        info,
        name: str,
        fullname: Optional[str] = None,
        parent: Optional[int] = None
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} adds team: {name}")
    cmd = AddTeam(
        user=user_id,
        name=name,
        fullname=fullname,
        parent=parent
    )
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("remove_team")
@graphql_payload
@require_authentication
async def remove_team(
        _,
        info,
        team: int
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} removes team: {team}")
    cmd = RemoveTeam(
        user=user_id,
        team=team
    )
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("edit_team")
@graphql_payload
@require_authentication
async def edit_team(
        _,
        info,
        team: int,
        name: str|None = None,
        fullname: str|None = None
) -> bool:
    user_id = info.context.get('user_id')

    logger.debug(f"User {user_id} edits team: {team}")
    cmd = UpdateTeam(
        user=user_id,
        team=team,
        name=name,
        fullname=fullname
    )
    await info.context['bus'].handle(cmd)
    return True

