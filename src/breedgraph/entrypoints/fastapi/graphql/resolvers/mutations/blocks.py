from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from src.breedgraph.domain.commands.blocks import (
    CreateUnit,
    AddPosition
)
from src.breedgraph.custom_exceptions import UnauthorisedOperationError

from typing import List, Any

import logging
logger = logging.getLogger(__name__)

from . import graphql_mutation

@graphql_mutation.field("blocks_create_unit")
@graphql_payload
@require_authentication
async def create_unit(
        _,
        info,
        unit: dict
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} adds unit: {unit}")
    cmd = CreateUnit(user=user_id, **unit)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("blocks_add_position")
@graphql_payload
@require_authentication
async def add_position(
        _,
        info,
        unit_id: int,
        position: dict
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} adds position: {unit_id}: {position}")
    cmd = AddPosition(user=user_id, unit=unit_id, **position)
    await info.context['bus'].handle(cmd)
    return True