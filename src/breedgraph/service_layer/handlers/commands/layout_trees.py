from asyncio import Queue
from breedgraph.domain import commands
from breedgraph.domain.model.layout_trees import LayoutInput
from breedgraph.domain.model.controls import Access, ControlledModelLabel
from breedgraph.domain.model.ontology import LayoutTypeStored, AxisType, OntologyEntryLabel

from breedgraph.service_layer.infrastructure import AbstractUnitOfWorkFactory

from ..registry import handlers

import logging
logger = logging.getLogger(__name__)

def validate_position_within_parent(position, parent_layout, parent_type):
    if not len(position) == len(parent_layout.axes):
        raise ValueError("Position array must be same length as the axes specified on the parent layout")
    for i, p in enumerate(position):
        if parent_type.axes[i] in [AxisType.COORDINATE, AxisType.CARTESIAN]:
            try:
                float(p)
            except ValueError:
                raise ValueError("Coordinate and Cartesian axes require numeric values")


@handlers.command_handler()
async def create_layout(
        cmd: commands.layout_trees.CreateLayout,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id, write_team=cmd.write_team, release=cmd.release) as uow:
        ontology_service = uow.ontology
        await ontology_service.require_entries([cmd.type_id], label=OntologyEntryLabel.LAYOUT_TYPE)
        layout_type = await ontology_service.get_entry(entry_id=cmd.type_id, label=LayoutTypeStored.label)
        if not len(layout_type.axes) == len(cmd.axes):
            raise ValueError("Axes names must be same length as specified by the LayoutType")

        layout_input = LayoutInput(
            name=cmd.name,
            type=cmd.type_id,
            location=cmd.location_id,
            axes=cmd.axes or []
        )

        if layout_input.location:
            # You can only link to what you can read
            await uow.controls.require_access(ControlledModelLabel.LOCATION, [layout_input.location], Access.READ)
        if cmd.parent:
            layout_tree = await uow.repositories.layout_trees.get(layout_id=cmd.parent)
            if layout_input.location:
                raise ValueError("Cannot set location on layout that is not the root of the layout tree")
            parent_layout = layout_tree.get_entry(cmd.parent)
            # the parent's type, as cited, so layouts can still be added to one of a removed type
            parent_type = await ontology_service.get_cited_entry(parent_layout.type, label=OntologyEntryLabel.LAYOUT_TYPE)
            position = cmd.position or []
            validate_position_within_parent(position, parent_layout, parent_type)
            layout_tree.add_layout(layout_input, parent_id=cmd.parent, position=cmd.position)
        else:
            await uow.repositories.layout_trees.create(layout_input)
        await uow.commit()



@handlers.command_handler()
async def update_layout(
        cmd: commands.layout_trees.UpdateLayout,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        layout_tree = await uow.repositories.layout_trees.get(layout_id=cmd.layout_id)
        if not layout_tree:
            raise ValueError("Layout not found")

        layout = layout_tree.get_entry(cmd.layout_id)

        if cmd.name and not cmd.name == layout.name:
            layout.name = cmd.name
        if cmd.location_id and not cmd.location_id == layout.location:
            if not layout_tree.root.location == cmd.location_id:
                raise ValueError("Cannot set location of layout that is not the root of the layout tree")
            await uow.controls.require_access(ControlledModelLabel.LOCATION, [cmd.location_id], Access.READ)
            layout.location = cmd.location_id

        # Other changes to layout are validated against the ontology
        if any([
            (cmd.type_id and not cmd.type_id == layout.type),
            (cmd.axes and not cmd.axes == layout.axes),
            (cmd.parent and not cmd.parent == layout_tree.get_parent_id(layout.id)),
            (cmd.position and not cmd.position == layout_tree.get_position(layout.id))
        ]):
            ontology_service = uow.ontology

            if any([
                (cmd.type_id and not cmd.type_id == layout.type),
                (cmd.axes and not cmd.axes == layout.axes)
            ]):
                if cmd.type_id and not cmd.type_id == layout.type:
                    await ontology_service.require_entries([cmd.type_id], label=OntologyEntryLabel.LAYOUT_TYPE)
                    layout_type = await ontology_service.get_entry(entry_id=cmd.type_id, label=LayoutTypeStored.label)
                else:
                    # the axes change: the layout's own type, as cited
                    layout_type = await ontology_service.get_cited_entry(layout.type, label=OntologyEntryLabel.LAYOUT_TYPE)
                if layout_type is None:
                    raise ValueError("Layout type not found")
                if not len(layout_type.axes) == len(cmd.axes if cmd.axes else layout.axes):
                    raise ValueError("Axes names must be same length as specified by the LayoutType")

                if cmd.type_id and not cmd.type_id == layout.type:
                    layout.type = cmd.type_id
                if cmd.axes and not cmd.axes == layout.axes:
                    layout.axes = cmd.axes

            if any([
                (cmd.parent and not cmd.parent == layout_tree.get_parent_id(layout.id)),
                (cmd.position and not cmd.position == layout_tree.get_position(layout.id))
            ]):
                # validate coordinates match parent layout type
                try:
                    parent_layout = layout_tree.get_entry(cmd.parent)
                    current_position = layout_tree.get_position(layout.id)

                    parent_type = await ontology_service.get_cited_entry(
                        parent_layout.type,
                        label=OntologyEntryLabel.LAYOUT_TYPE
                    )
                    position = cmd.position or []
                    validate_position_within_parent(position, parent_layout, parent_type)

                    if cmd.position and not cmd.position == current_position:
                        layout_tree.change_parent(layout.id, cmd.parent, cmd.position)
                    else:
                        layout_tree.change_parent(layout.id, cmd.parent)

                except KeyError:
                    raise ValueError('The provided parent ID is not in the same layout tree')
        await uow.commit()


@handlers.command_handler()
async def delete_layout(
        cmd: commands.layout_trees.DeleteLayout,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        layout_tree = await uow.repositories.layout_trees.get(layout_id=cmd.layout_id)

        if layout_tree.root.id == cmd.layout_id:
            await uow.repositories.layout_trees.remove(layout_tree)
        else:
            layout_tree.remove_layout(cmd.layout_id)

        await uow.commit()

