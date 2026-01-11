from src.breedgraph.service_layer.infrastructure import AbstractUnitOfWork, AbstractUnitHolder
from src.breedgraph.domain import commands
from src.breedgraph.domain.model.blocks import UnitInput, Position
from src.breedgraph.domain.model.ontology import AxisType, OntologyEntryLabel


from ..registry import handlers

import logging
logger = logging.getLogger(__name__)

@handlers.command_handler()
async def create_unit(
        cmd: commands.blocks.CreateUnit,
        uow: AbstractUnitOfWork
):
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        unit_input = UnitInput(
            subject = cmd.subject_id,
            germplasm = cmd.germplasm_id,
            name = cmd.name,
            description = cmd.description
        )
        if cmd.parents:
            block = await uow.repositories.blocks.get(unit_id=cmd.parents[0])
            unit_id = block.add_unit(unit_input, parents=cmd.parents)
        else:
            block = await uow.repositories.blocks.create(unit_input)
            unit_id = block.get_root_id()

        for child in cmd.children or []:
            if child in block.entries:
                block.set_child(source_id=unit_id, sink_id=child)
            else:
                child_block = await uow.repositories.blocks.get(unit_id=child)
                if not child_block.get_root_id() == child:
                    raise ValueError("Merging blocks requires all children to be the root of their respective block")
                block.merge_block(block=child_block, parents=[unit_id])

        if cmd.location_id:
            position = Position(
                location_id=cmd.location_id,
                layout_id=cmd.layout_id,
                coordinates=cmd.coordinates,
                start=cmd.start,
                end=cmd.end
            )
            await _validate_position(uow, position)
            unit = block.get_unit(unit_id)
            unit.positions.append(position)

        await uow.commit()

@handlers.command_handler()
async def update_unit(
        cmd: commands.blocks.UpdateUnit,
        uow: AbstractUnitOfWork
):
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        block = await uow.repositories.blocks.get(unit_id=cmd.unit_id)
        unit = block.get_unit(cmd.unit_id)

        # Update unit fields if provided
        if cmd.subject_id is not None:
            unit.subject = cmd.subject_id
        if cmd.germplasm_id is not None:
            unit.germplasm = cmd.germplasm_id
        if cmd.name is not None:
            unit.name = cmd.name
        if cmd.description is not None:
            unit.description = cmd.description

        # Handle parent/child relationships if provided, children first as we may split blocks after
        if cmd.children is not None:
            # Remove existing child relationships and add new ones
            block.change_children(cmd.children)

        if cmd.parents is not None:
            if len(cmd.parents) == 0:
                if block.get_parent_ids(cmd.unit_id):
                    # this node is a child of this block, so removing its parents will make it the root of a new block
                    await uow.extra.split_block(block, cmd.unit_id)
                else:
                    logger.debug('Updating a block root unit to empty parents, doing nothing')
            elif block.get_parent_ids(cmd.unit_id):
                block.change_parents(unit.id, cmd.parents)
            else:
                # get the new parents block to merge blocks
                new_block = await uow.repositories.blocks.get(unit_id=cmd.parents[0])
                new_block.merge_block(block, parents=cmd.parents)

        await uow.commit()

@handlers.command_handler()
async def delete_unit(
        cmd: commands.blocks.DeleteUnit,
        uow: AbstractUnitOfWork
):
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        block = await uow.repositories.blocks.get(unit_id=cmd.unit_id)
        block.remove_unit(cmd.unit_id)
        await uow.commit()

@handlers.command_handler()
async def add_position(
        cmd: commands.blocks.AddPosition,
        uow: AbstractUnitOfWork
):
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        block = await uow.repositories.blocks.get(unit_id=cmd.unit_id)
        position = Position(
            location_id=cmd.location_id,
            layout_id=cmd.layout_id,
            coordinates=cmd.coordinates,
            start=cmd.start,
            end=cmd.end
        )
        await _validate_position(uow, position)
        unit = block.get_unit(cmd.unit_id)
        unit.positions.append(position)
        await uow.commit()

async def _validate_position(uow: AbstractUnitHolder, position: Position):
    if not position.location_id:
        raise ValueError("Positions require location_id")

    if position.layout_id:
        if not position.coordinates:
            raise ValueError("Coordinates required if a layout is specified")

        arrangement = await uow.repositories.arrangements.get(layout_id=position.layout_id)
        layout = arrangement.get_layout(position.layout_id)
        if not len(position.coordinates) == len(layout.axes):
            raise ValueError(f"Coordinates must match the length of specified layout axes")
        if not layout.location == position.location_id:
            raise ValueError("Layout location does not match the position location")

        layout_type = await uow.ontology.get_entry(entry_id=layout.type, label=OntologyEntryLabel.LAYOUT_TYPE)
        for i, p in enumerate(position.coordinates):
            if layout_type.axes[i] in [AxisType.COORDINATE, AxisType.CARTESIAN]:
                try:
                    float(p)
                except ValueError:
                    raise ValueError("Coordinate and Cartesian positions require numeric values")

@handlers.command_handler()
async def remove_position(
        cmd: commands.blocks.RemovePosition,
        uow: AbstractUnitOfWork
):
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        block = await uow.repositories.blocks.get(unit_id=cmd.unit_id)
        position = Position(
            location_id=cmd.location_id,
            layout_id=cmd.layout_id,
            coordinates=cmd.coordinates,
            start=cmd.start,
            end=cmd.end
        )
        unit = block.get_unit(cmd.unit_id)
        try:
            unit.positions.remove(position)
        except ValueError:
            raise ValueError("A position matching the provided details was not found, nothing changed")
        await uow.commit()