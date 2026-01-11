from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from src.breedgraph.domain.commands.blocks import (
    CreateUnit,
    UpdateUnit,
    DeleteUnit,
    AddPosition,
    RemovePosition
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
        unit: dict,
        position: dict = None
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} adds unit: {unit}")
    cmd = CreateUnit(
        agent_id=user_id,
        name=unit.get('name'),
        description=unit.get('description'),
        subject_id=unit.get('subject_id'),
        germplasm_id=unit.get('germplasm_id'),
        parents=unit.get('parent_ids'),
        children=unit.get('children_ids'),
        location_id = position.get('location_id') if position else None,
        layout_id = position.get('layout_id') if position else None,
        coordinates = position.get('coordinates') if position else None,
        start = position.get('start') if position else None,
        end = position.get('end') if position else None
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
        description=unit.get('description'),
        subject_id=unit.get('subject_id'),
        germplasm_id=unit.get('germplasm_id'),
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

@graphql_mutation.field("blocksRemovePosition")
@graphql_payload
@require_authentication
async def remove_position(
        _,
        info,
        unit_id: int,
        position: dict
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} removes position: {unit_id}: {position}")
    cmd = RemovePosition(
        agent_id=user_id,
        unit_id=unit_id,
        **position
    )
    await info.context['bus'].handle(cmd)
    return True
