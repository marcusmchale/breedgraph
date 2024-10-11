from src.breedgraph.service_layer import unit_of_work
from src.breedgraph.domain import commands
from src.breedgraph.domain.model.blocks import UnitInput, Position
from src.breedgraph.domain.model.controls import ReadRelease
import logging

logger = logging.getLogger(__name__)

async def add_unit(
        cmd: commands.blocks.AddUnit,
        uow: unit_of_work.AbstractUnitOfWork
):
    kwargs = cmd.model_dump()
    async with uow.get_repositories(user_id=kwargs.pop('user'), release=ReadRelease[cmd.release]) as uow:
        unit_input = UnitInput(**kwargs)
        if cmd.parents:
            block = await uow.blocks.get(unit_id=cmd.parents[0])
            unit_id = block.add_unit(unit_input, parents=cmd.parents)
        else:
            block = await uow.blocks.create(unit_input)
            unit_id = block.get_root_id()

        for child in cmd.children if cmd.children else []:
            if child in block.entries:
                block.set_child(source_id=unit_id, sink_id=child)
            else:
                child_block = await uow.blocks.get(unit_id=child)
                if not child_block.get_root_id() == child:
                    raise ValueError("Merging blocks requires all children to be the root of their respective block")
                block.merge_block(block=child_block, parents=[unit_id])

        await uow.commit()


async def add_position(
        cmd: commands.blocks.AddPosition,
        uow: unit_of_work.AbstractUnitOfWork
):
    kwargs = cmd.model_dump()
    async with uow.get_repositories(user_id=kwargs.pop('user')) as uow:
        unit_id = kwargs.pop('unit')
        block = await uow.blocks.get(unit_id=unit_id)

        if cmd.layout:
            arrangement = await uow.arrangements.get(layout_id=cmd.layout)
            layout = arrangement.get_layout(cmd.layout)
            if not layout.location == cmd.location:
                raise ValueError("Layout must be for the given location")
            if not cmd.coordinates:
                raise ValueError("Coordinates required for layout")
            elif not len(cmd.coordinates) == len(layout.axes):
                raise ValueError(f"This layout requires {layout.axes} coordinate values")

        unit = block.get_unit(unit_id)
        unit.positions.append(Position(**kwargs))
        await uow.commit()
