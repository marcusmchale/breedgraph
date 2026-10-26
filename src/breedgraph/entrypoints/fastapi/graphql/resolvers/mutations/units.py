from breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from breedgraph.domain.commands.unit_graphs import (
    CreateUnit,
    UpdateUnit,
    DeleteUnit,
    AddPosition,
    RemovePosition,
    MoveUnits,
    PlaceUnits,
    UnitPlacement,
    ChangePositions,
    DeriveUnits,
    AddChildren
)
from breedgraph.domain.model.unit_graphs import UnitOutput, CHILD_NAME_TEMPLATE
from breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import update_units_map
from breedgraph.domain.model.controls import ReadRelease

from typing import List


import logging
logger = logging.getLogger(__name__)

from . import graphql_mutation

@graphql_mutation.field("unitsCreateUnit")
@graphql_payload
@require_authentication
async def create_unit(
        _,
        info,
        unit: dict,
        position: dict|None = None,
        control_team_id: int | None = None,
        release: ReadRelease = ReadRelease.PRIVATE
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} adds unit: {unit}")
    cmd = CreateUnit(
        agent_id=user_id,
        write_team=control_team_id,
        release=release,
        name=unit.get('name'),
        description=unit.get('description'),
        subject_id=unit.get('subject_id'),
        germplasm_id=unit.get('germplasm_id'),
        parents=unit.get('parent_ids'),
        children=unit.get('children_ids'),
        derived_from=unit.get('derived_from'),
        location_id = position.get('location_id') if position else None,
        layout_id = position.get('layout_id') if position else None,
        coordinates = position.get('coordinates') if position else None,
        start = position.get('start') if position else None,
        end = position.get('end') if position else None
    )

    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("unitsUpdateUnit")
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
        unit_id=unit.get('id'),
        parents=unit.get('parent_ids'),
        children=unit.get('children_ids'),
        derived_from=unit.get('derived_from'),
        # passed only when given, as null removes or clears them
        **{key: unit[key] for key in ('name', 'description', 'subject_id', 'germplasm_id') if key in unit}
    )
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("unitsDeleteUnit")
@graphql_payload
@require_authentication
async def delete_unit(
        _,
        info,
        id: int
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} deletes unit: {id}")
    cmd = DeleteUnit(agent_id=user_id, unit_id=id)
    await info.context['bus'].handle(cmd)
    return True


@graphql_mutation.field("unitsAddPosition")
@graphql_payload
@require_authentication
async def add_position(
        _,
        info,
        id: int,
        position: dict
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} adds position: {id}: {position}")
    cmd = AddPosition(
        agent_id=user_id,
        unit_id=id,
        **position
    )
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("unitsRemovePosition")
@graphql_payload
@require_authentication
async def remove_position(
        _,
        info,
        id: int,
        position: dict
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} removes position: {id}: {position}")
    cmd = RemovePosition(
        agent_id=user_id,
        unit_id=id,
        **position
    )
    await info.context['bus'].handle(cmd)
    return True


async def _units(info, unit_ids: List[int]) -> List[UnitOutput]:
    """The units as they now are, read once the command has committed"""
    await update_units_map(info.context, unit_ids=unit_ids)
    units_map = info.context.get('units_map', {})
    return [units_map[unit_id] for unit_id in unit_ids if unit_id in units_map]

@graphql_mutation.field("unitsMoveUnits")
@graphql_payload
@require_authentication
async def move_units(
        _,
        info,
        units: dict,
        position: dict
) -> List[UnitOutput]:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} moves units: {units} to {position}")
    cmd = MoveUnits(agent_id=user_id, units=units, **position)
    return await _units(info, await info.context['bus'].handle(cmd))

@graphql_mutation.field("unitsPlaceUnits")
@graphql_payload
@require_authentication
async def place_units(
        _,
        info,
        placements: List[dict]
) -> List[UnitOutput]:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} places {len(placements)} units")
    cmd = PlaceUnits(agent_id=user_id, placements=[
        # the germplasm passed only when given, as null removes it
        UnitPlacement(
            unit_id=placement['unit_id'],
            **(placement.get('position') or {}),
            **({'germplasm_id': placement['germplasm_id']} if 'germplasm_id' in placement else {})
        )
        for placement in placements
    ])
    return await _units(info, await info.context['bus'].handle(cmd))

@graphql_mutation.field("unitsChangePositions")
@graphql_payload
@require_authentication
async def change_positions(
        _,
        info,
        units: dict,
        at: dict,
        change: dict
) -> List[UnitOutput]:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} changes positions of units: {units} at {at}: {change}")
    cmd = ChangePositions(agent_id=user_id, units=units, at=at, change=change)
    return await _units(info, await info.context['bus'].handle(cmd))

@graphql_mutation.field("unitsDeriveUnits")
@graphql_payload
@require_authentication
async def derive_units(
        _,
        info,
        units: dict,
        control_team_id: int,
        parent_ids: List[int] | None = None,
        position: dict | None = None,
        subject_id: int | None = None,
        stage: str | None = None,
        description: str | None = None,
        germplasm_id: int | None = None,
        copy_germplasm: bool | None = None,
        release: ReadRelease = ReadRelease.PRIVATE
) -> List[UnitOutput]:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} derives units from: {units}")
    cmd = DeriveUnits(
        agent_id=user_id,
        write_team=control_team_id,
        release=release,
        units=units,
        parents=parent_ids,
        subject_id=subject_id,
        description=description,
        germplasm_id=germplasm_id,
        # given as null, the defaults hold
        **({'stage': stage} if stage is not None else {}),
        **({'copy_germplasm': copy_germplasm} if copy_germplasm is not None else {}),
        **(position or {})
    )
    return await _units(info, await info.context['bus'].handle(cmd))

@graphql_mutation.field("unitsAddChildren")
@graphql_payload
@require_authentication
async def add_children(
        _,
        info,
        parents: dict,
        subject_id: int,
        control_team_id: int,
        count: int | None = None,
        name: str | None = CHILD_NAME_TEMPLATE,
        description: str | None = None,
        germplasm_id: int | None = None,
        start=None,
        release: ReadRelease = ReadRelease.PRIVATE
) -> List[UnitOutput]:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} adds children to: {parents}")
    cmd = AddChildren(
        agent_id=user_id,
        write_team=control_team_id,
        release=release,
        parents=parents,
        subject_id=subject_id,
        description=description,
        germplasm_id=germplasm_id,
        start=start,
        # a name given as null leaves them unnamed; a count given as null is the default
        name=name,
        **({'count': count} if count is not None else {})
    )
    return await _units(info, await info.context['bus'].handle(cmd))
