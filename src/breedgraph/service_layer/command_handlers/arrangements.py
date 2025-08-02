import logging

from src.breedgraph.domain import commands
from src.breedgraph.domain.model.controls import ReadRelease
from src.breedgraph.domain.model.arrangements import Arrangement, LayoutInput, LayoutStored
from src.breedgraph.domain.model.ontology import AxisType

from src.breedgraph.service_layer import unit_of_work

logger = logging.getLogger(__name__)

async def add_layout(
        cmd: commands.arrangements.CreateLayout,
        uow: unit_of_work.AbstractUnitOfWork
):
    async with uow.get_repositories(user_id=cmd.user, release=ReadRelease[cmd.release]) as uow:
        ontology = await uow.ontologies.get()
        if not cmd.type in ontology.entries:
            raise ValueError("New layouts must use types specified in the latest ontology")

        layout_type = ontology.get_entry_model(cmd.type, label="LayoutType")
        if layout_type is None:
            raise ValueError("Layout type not found")
        if not len(layout_type.axes) == len(cmd.axes):
            raise ValueError("Axes names must be same length as specified by the LayoutType")

        if cmd.parent is None:
            layout_input = LayoutInput(**cmd.model_dump())
            await uow.arrangements.create(layout_input)
        else:
            arrangement = await uow.arrangements.get(layout_id=cmd.parent)
            parent_layout = arrangement.get_entry(cmd.parent)
            if not len(cmd.position) == len(parent_layout.axes):
                raise ValueError("Position must be same length as parent axes")

            if not parent_layout.type in ontology.entries:
                ontology = await uow.ontologies.get(entry_id=parent_layout.id)

            parent_type = ontology.get_entry_model(entry=parent_layout.type, label="LayoutType")

            for i, p in enumerate(cmd.position):
                if parent_type.axes[i] in [AxisType.COORDINATE, AxisType.CARTESIAN]:
                    try:
                        float(p)
                    except ValueError:
                        raise ValueError("Coordinate and Cartesian axes require numeric values")

            arrangement.add_layout(LayoutInput(**cmd.model_dump()), parent_id=cmd.parent, position=cmd.position)
        await uow.commit()
