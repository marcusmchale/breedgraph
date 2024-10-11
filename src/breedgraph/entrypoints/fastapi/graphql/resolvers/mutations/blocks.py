from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload
from src.breedgraph.domain.commands.blocks import (
    AddUnit,
    AddPosition
)
from src.breedgraph.custom_exceptions import UnauthorisedOperationError
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.mutations import graphql_mutation

from typing import List, Any

import logging
logger = logging.getLogger(__name__)

@graphql_mutation.field("blocks_add_unit")
@graphql_payload
async def add_unit(
        _,
        info,
        unit: dict
) -> bool:
    user_id = info.context.get('user_id')
    if user_id is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    logger.debug(f"User {user_id} adds unit: {unit}")
    cmd = AddUnit(user=user_id, **unit)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("blocks_add_position")
@graphql_payload
async def add_position(
        _,
        info,
        unit_id: int,
        position: dict
) -> bool:
    user_id = info.context.get('user_id')
    if user_id is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    if position.get('coordinates') is not None:
        for i, value in enumerate(position.get('coordinates')):
            values = list(value.values())
            if len(values) != 1:
                raise ValueError("A single value should be provided per CoordinateValue")
            position.get('coordinates')[i] = values[0]

    logger.debug(f"User {user_id} adds position: {unit_id}: {position}")
    cmd = AddPosition(user=user_id, unit=unit_id, **position)
    await info.context['bus'].handle(cmd)
    return True