from src.breedgraph.domain import commands
from src.breedgraph.domain.model.arrangements import LayoutInput
from src.breedgraph.domain.model.ontology import LayoutTypeStored, AxisType, OntologyEntryLabel

from src.breedgraph.service_layer.infrastructure import AbstractUnitOfWork

from ..registry import handlers

import logging
logger = logging.getLogger(__name__)

@handlers.command_handler()
async def create_layout(
        cmd: commands.arrangements.CreateLayout,
        uow: AbstractUnitOfWork
):
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        ontology_service = uow.ontology
        layout_type = await ontology_service.get_entry(entry_id=cmd.type_id, label=LayoutTypeStored.label)
        if layout_type is None:
            raise ValueError("Layout type not found")
        if not len(layout_type.axes) == len(cmd.axes):
            raise ValueError("Axes names must be same length as specified by the LayoutType")

        layout_input = LayoutInput(
            name=cmd.name,
            type=cmd.type_id,
            location=cmd.location_id,
            axes=cmd.axes or []
        )

        if cmd.parent:
            arrangement = await uow.repositories.arrangements.get(layout_id=cmd.parent)
            parent_layout = arrangement.get_entry(cmd.parent)
            parent_type = await ontology_service.get_entry(entry_id=parent_layout.type, label=OntologyEntryLabel.LAYOUT_TYPE)
            position = cmd.position or []
            if not len(position) == len(parent_layout.axes):
                raise ValueError("Position array must be same length as the axes specified on the parent layout")
            for i, p in enumerate(position):
                if parent_type.axes[i] in [AxisType.COORDINATE, AxisType.CARTESIAN]:
                    try:
                        float(p)
                    except ValueError:
                        raise ValueError("Coordinate and Cartesian axes require numeric values")

            arrangement.add_layout(layout_input, parent_id=cmd.parent, position=cmd.position)
        else:
            await uow.repositories.arrangements.create(layout_input)
        await uow.commit()






