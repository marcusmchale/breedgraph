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
    kwargs = cmd.model_dump()
    async with uow.get_uow(user_id=kwargs.pop('user'), release=ReadRelease[cmd.release]) as uow:
        unit_input = UnitInput(**kwargs)
        if cmd.parents:
            block = await uow.repositories.blocks.get(unit_id=cmd.parents[0])
            unit_id = block.add_unit(unit_input, parents=cmd.parents)
        else:
            block = await uow.repositories.blocks.create(unit_input)
            unit_id = block.get_root_id()

        for child in cmd.children if cmd.children else []:
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
    kwargs = cmd.model_dump(exclude_unset=True)
    user_id = kwargs.pop('user')
    unit_id = kwargs.pop('unit_id')

    release = ReadRelease[cmd.release] if cmd.release else ReadRelease.REGISTERED
    async with uow.get_uow(user_id=user_id, release=release) as uow:
        block = await uow.repositories.blocks.get(unit_id=unit_id)
        unit = block.get_unit(unit_id)

        # Update unit fields if provided
        if 'subject' in kwargs:
            unit.subject = kwargs['subject']
        if 'name' in kwargs:
            unit.name = kwargs['name']
        if 'synonyms' in kwargs:
            unit.synonyms = kwargs['synonyms']
        if 'description' in kwargs:
            unit.description = kwargs['description']

        # Handle parent/child relationships if provided
        if cmd.parents is not None:
            # Remove existing parent relationships and add new ones
            block.clear_parents(unit_id)
            for parent_id in cmd.parents:
                block.set_parent(source_id=parent_id, sink_id=unit_id)

        if cmd.children is not None:
            # Remove existing child relationships and add new ones
            block.clear_children(unit_id)
            for child_id in cmd.children:
                if child_id in block.entries:
                    block.set_child(source_id=unit_id, sink_id=child_id)
                else:
                    child_block = await uow.repositories.blocks.get(unit_id=child_id)
                    if not child_block.get_root_id() == child_id:
                        raise ValueError(
                            "Merging blocks requires all children to be the root of their respective block")
                    block.merge_block(block=child_block, parents=[unit_id])

        await uow.commit()

@handlers.command_handler()
async def delete_unit(
        cmd: commands.blocks.DeleteUnit,
        uow: AbstractUnitOfWork
):
    async with uow.get_uow(user_id=cmd.user) as uow:
        block = await uow.repositories.blocks.get(unit_id=cmd.unit_id)
        block.remove_unit(cmd.unit_id)
        await uow.commit()

@handlers.command_handler()
async def add_position(
        cmd: commands.blocks.AddPosition,
        uow: AbstractUnitOfWork
):
    kwargs = cmd.model_dump()
    async with uow.get_uow(user_id=kwargs.pop('user')) as uow:
        unit_id = kwargs.pop('unit')
        block = await uow.repositories.blocks.get(unit_id=unit_id)

        if cmd.layout:
            if not cmd.coordinates:
                raise ValueError("Coordinates required if a layout is specified")

            arrangement = await uow.repositories.arrangements.get(layout_id=cmd.layout)
            layout = arrangement.get_layout(cmd.layout)
            if not len(cmd.coordinates) == len(layout.axes):
                raise ValueError(f"Coordinates must match the length of specified layout axes")
            if not layout.location == cmd.location:
                raise ValueError("Layout location does not match the provided location")

            ontology = await uow.repositories.ontologies.get(entry_id=layout.type)
            layout_type_id, layout_type = ontology.get_entry(layout.type)
            for i, p in enumerate(cmd.coordinates):
                if layout_type.axes[i] in [AxisType.COORDINATE, AxisType.CARTESIAN]:
                    try:
                        float(p)
                    except ValueError:
                        raise ValueError("Coordinate and Cartesian positions require numeric values")

        unit = block.get_unit(unit_id)
        unit.positions.append(Position(**kwargs))
        await uow.commit()
