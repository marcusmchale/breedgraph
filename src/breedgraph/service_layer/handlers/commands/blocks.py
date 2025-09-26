from src.breedgraph.domain import commands
from src.breedgraph.domain.model.blocks import UnitInput, Position
from src.breedgraph.domain.model.ontology import AxisType
from src.breedgraph.domain.model.controls import ReadRelease

from src.breedgraph.service_layer.infrastructure import AbstractUnitOfWork

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
        if cmd.subject is not None:
            unit.subject = cmd.subject_id
        if cmd.name is not None:
            unit.name = cmd.name
        if cmd.description is not None:
            unit.description = cmd.description

        # Handle parent/child relationships if provided
        if cmd.parents is not None:
            # Remove existing parent relationships and add new ones
            block.clear_parents(cmd.unit_id)
            for parent_id in cmd.parents:
                block.set_parent(source_id=parent_id, sink_id=cmd.unit_id)

        if cmd.children is not None:
            # Remove existing child relationships and add new ones
            block.clear_children(cmd.unit_id)
            for child_id in cmd.children:
                if child_id in block.entries:
                    block.set_child(source_id=cmd.unit_id, sink_id=child_id)
                else:
                    child_block = await uow.repositories.blocks.get(unit_id=child_id)
                    if not child_block.get_root_id() == child_id:
                        raise ValueError(
                            "Merging blocks requires all children to be the root of their respective block")
                    block.merge_block(block=child_block, parents=[cmd.unit_id])

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

        if cmd.layout_id:
            if not cmd.coordinates:
                raise ValueError("Coordinates required if a layout is specified")

            arrangement = await uow.repositories.arrangements.get(layout_id=cmd.layout_id)
            layout = arrangement.get_layout(cmd.layout_id)
            if not len(cmd.coordinates) == len(layout.axes):
                raise ValueError(f"Coordinates must match the length of specified layout axes")
            if not layout.location == cmd.location_id:
                raise ValueError("Layout location does not match the provided location")

            layout_type = await uow.ontology.get_entry(entry_id=layout.type)
            for i, p in enumerate(cmd.coordinates):
                if layout_type.axes[i] in [AxisType.COORDINATE, AxisType.CARTESIAN]:
                    try:
                        float(p)
                    except ValueError:
                        raise ValueError("Coordinate and Cartesian positions require numeric values")

        unit = block.get_unit(cmd.unit_id)
        unit.positions.append(
            Position(
                location=cmd.location_id,
                layout=cmd.layout_id,
                coordinates=cmd.coordinates,
                start=cmd.start,
                end=cmd.end
            )
        )
        await uow.commit()
