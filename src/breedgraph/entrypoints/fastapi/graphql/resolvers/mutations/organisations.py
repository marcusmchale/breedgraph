from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from src.breedgraph.domain.commands.organisations import (
    CreateTeam, DeleteTeam, UpdateTeam
)

from typing import Optional

import logging
logger = logging.getLogger(__name__)

from . import graphql_mutation

@graphql_mutation.field("organisationsCreateTeam")
@graphql_payload
@require_authentication
async def create_team(
        _,
        info,
        name: str,
        fullname: Optional[str] = None,
        parent_id: Optional[int] = None
) -> bool:
    user_id: int = info.context.get('user_id')
    logger.debug(f"User {user_id} creates team: {name}")
    cmd = CreateTeam(
        agent_id=user_id,
        name=name,
        fullname=fullname,
        parent=parent_id
    )
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("organisationsDeleteTeam")
@graphql_payload
@require_authentication
async def delete_team(
        _,
        info,
        team_id: int
) -> bool:
    user_id: int = info.context.get('user_id')
    logger.debug(f"User {user_id} deletes team: {team_id}")
    cmd = DeleteTeam(
        agent_id=user_id,
        team_id=team_id
    )
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("organisationsUpdateTeam")
@graphql_payload
@require_authentication
async def update_team(
        _,
        info,
        team_id: int,
        name: str|None = None,
        fullname: str|None = None
) -> bool:
    user_id = info.context.get('user_id')

    logger.debug(f"User {user_id} updates team: {team_id}")
    cmd = UpdateTeam(
        agent_id=user_id,
        team_id=team_id,
        name=name,
        fullname=fullname
    )
    await info.context['bus'].handle(cmd)
    return True

