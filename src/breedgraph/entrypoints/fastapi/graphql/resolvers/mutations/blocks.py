from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from src.breedgraph.domain.commands.blocks import (
    CreateUnit,
    UpdateUnit,
    DeleteUnit,
    AddPosition
)

import logging
logger = logging.getLogger(__name__)

from . import graphql_mutation

@graphql_mutation.field("blocksCreateUnit")
@graphql_payload
@require_authentication
async def create_unit(
        _,
        info,
        unit: dict
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} adds unit: {unit}")
    cmd = CreateUnit(
        agent_id=user_id,
        name=unit.get('name'),
        synonyms=unit.get('synonyms'),
        description=unit.get('description'),
        subject_id=unit.get('subject_id'),
        parents=unit.get('parent_ids'),
        children=unit.get('children_ids')
    )
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("blocksUpdateUnit")
@graphql_payload
@require_authentication
async def update_unit(
        _,
        info,
        unit: dict
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} updates unit: {unit}")
    cmd = UpdateUnit(
        agent_id=user_id,
        unit_id=unit.get('unit_id'),
        name=unit.get('name'),
        synonyms=unit.get('synonyms'),
        description=unit.get('description'),
        subject_id=unit.get('subject_id'),
        parents=unit.get('parent_ids'),
        children=unit.get('children_ids')
    )
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("blocksDeleteUnit")
@graphql_payload
@require_authentication
async def delete_unit(
        _,
        info,
        unit_id: int
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} deletes unit: {unit_id}")
    cmd = DeleteUnit(agent_id=user_id, unit_id=unit_id)
    await info.context['bus'].handle(cmd)
    return True


@graphql_mutation.field("blocksAddPosition")
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
    cmd = AddPosition(
        agent_id=user_id,
        unit_id=unit_id,
        **position
    )
    await info.context['bus'].handle(cmd)
    return True