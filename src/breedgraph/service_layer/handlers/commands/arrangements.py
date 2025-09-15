from src.breedgraph.domain import commands
from src.breedgraph.domain.model.controls import ReadRelease
from src.breedgraph.domain.model.arrangements import LayoutInput
from src.breedgraph.domain.model.ontology import LayoutTypeStored
from src.breedgraph.domain.model.ontology import AxisType

from src.breedgraph.service_layer.infrastructure import AbstractUnitOfWork

from ..registry import handlers

import logging
logger = logging.getLogger(__name__)

@handlers.command_handler()
async def add_layout(
        cmd: commands.arrangements.CreateLayout,
        uow: AbstractUnitOfWork
):
    async with (uow.get_uow(user_id=cmd.user, release=ReadRelease[cmd.release]) as uow):
        ontology_service = uow.ontology
        layout_type = await ontology_service.get_entry(entry_id=cmd.type, label=LayoutTypeStored.label)
        if layout_type is None:
            raise ValueError("Layout type not found")
        if not len(layout_type.axes) == len(cmd.axes):
            raise ValueError("Axes names must be same length as specified by the LayoutType")

        cmd_dump = cmd.model_dump()
        cmd_dump.pop('user')
        cmd_dump.pop('release')
        if cmd.parent is None:
            cmd_dump.pop('parent')
            cmd_dump.pop('position')
            layout_input = LayoutInput(**cmd_dump)
            await uow.repositories.arrangements.create(layout_input)
        else:
            parent = cmd_dump.pop('parent')
            position = cmd_dump.pop('position') or []
            arrangement = await uow.repositories.arrangements.get(layout_id=parent)
            parent_layout = arrangement.get_entry(parent)

            if not len(position) == len(parent_layout.axes):
                raise ValueError("Position must be same length as parent axes")

            parent_type = await ontology_service.get_entry(entry_id=parent_layout.type, label="LayoutType")
            for i, p in enumerate(position):
                if parent_type.axes[i] in [AxisType.COORDINATE, AxisType.CARTESIAN]:
                    try:
                        float(p)
                    except ValueError:
                        raise ValueError("Coordinate and Cartesian axes require numeric values")

            arrangement.add_layout(LayoutInput(**cmd_dump), parent_id=cmd.parent, position=cmd.position)
        await uow.commit()
