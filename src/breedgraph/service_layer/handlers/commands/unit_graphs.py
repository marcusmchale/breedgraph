from breedgraph.custom_exceptions import NoResultFoundError, IllegalOperationError
from breedgraph.service_layer.infrastructure import AbstractUnitOfWorkFactory, AbstractUnitHolder
from breedgraph.domain import commands
from breedgraph.domain.model.unit_graphs import UnitInput, Position
from breedgraph.domain.model.ontology import AxisType, OntologyEntryLabel, LayoutTypeStored
from breedgraph.domain.model.controls import Access, ControlledModelLabel


from ..registry import handlers

import logging
logger = logging.getLogger(__name__)

@handlers.command_handler()
async def create_unit(
        cmd: commands.unit_graphs.CreateUnit,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id, write_team=cmd.write_team, release=cmd.release) as uow:
        unit_input = UnitInput(
            subject = cmd.subject_id,
            germplasm = cmd.germplasm_id,
            name = cmd.name,
            description = cmd.description
        )
        if cmd.parents:
            unit_graph = await uow.repositories.unit_graphs.get(unit_id=cmd.parents[0])
            if not unit_graph:
                raise ValueError("Unit graph not found")
            unit_id = unit_graph.add_unit(unit_input, parents=cmd.parents)
        else:
            if not cmd.location_id:
                raise ValueError("New unit graphs must have a location specified")
            unit_graph = await uow.repositories.unit_graphs.create(unit_input)
            unit_id = unit_graph.get_root_id()

        for child in cmd.children or []:
            if child in unit_graph.entries:
                unit_graph.set_child(source_id=unit_id, sink_id=child)
            else:
                child_unit_graph = await uow.repositories.unit_graphs.get(unit_id=child)
                if not child_unit_graph:
                    raise ValueError("Child unit graph not found")
                if not child_unit_graph.get_root_id() == child:
                    raise ValueError("Merging unit graphs requires all children to be the root of their respective unit graph")
                unit_graph.merge_unit_graph(unit_graph=child_unit_graph, parents=[unit_id])

        if cmd.location_id:
            position = Position(
                location_id=cmd.location_id,
                layout_id=cmd.layout_id,
                coordinates=cmd.coordinates,
                start=cmd.start,
                end=cmd.end
            )

            await _validate_position_layout(uow, position)
            unit_graph.add_position(unit_id, position)

        await uow.commit()

@handlers.command_handler()
async def update_unit(
        cmd: commands.unit_graphs.UpdateUnit,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        unit_graph = await uow.repositories.unit_graphs.get(unit_id=cmd.unit_id)
        unit = unit_graph.get_unit(cmd.unit_id)

        # Update unit fields if provided; given as None, the subject and germplasm are removed
        if 'subject_id' in cmd.model_fields_set:
            unit.subject = cmd.subject_id
        if 'germplasm_id' in cmd.model_fields_set:
            unit.germplasm = cmd.germplasm_id
        if cmd.name is not None:
            unit.name = cmd.name
        if cmd.description is not None:
            unit.description = cmd.description

        # Handle parent/child relationships if provided, children first as we may split unit graphs after
        if cmd.children is not None:
            # Remove existing child relationships and add new ones
            unit_graph.change_children(cmd.children)

        if cmd.parents is not None:
            if len(cmd.parents) == 0:
                if unit_graph.get_parent_ids(cmd.unit_id):
                    # this node is a child of this unit graph, so removing its parents will make it the root of a new unit graph
                    await uow.controls.require_access(ControlledModelLabel.UNIT, [cmd.unit_id], Access.CURATE)
                    await uow.controls.require_access(ControlledModelLabel.UNIT, unit_graph.get_parent_ids(cmd.unit_id), Access.READ)
                    await uow.restructuring.split_unit_graph(unit_graph, cmd.unit_id)
                else:
                    logger.debug('Updating a unit graph root unit to empty parents, doing nothing')
            elif unit_graph.get_parent_ids(cmd.unit_id):
                unit_graph.change_parents(unit.id, cmd.parents)
            else:
                # get the new parents unit graph to merge unit graphs
                new_unit_graph = await uow.repositories.unit_graphs.get(unit_id=cmd.parents[0])
                new_unit_graph.merge_unit_graph(unit_graph, parents=cmd.parents)

        await uow.commit()

@handlers.command_handler()
async def delete_unit(
        cmd: commands.unit_graphs.DeleteUnit,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        unit_graph = await uow.repositories.unit_graphs.get(unit_id=cmd.unit_id)
        unit_graph.remove_unit(cmd.unit_id)
        await uow.commit()

@handlers.command_handler()
async def add_position(
        cmd: commands.unit_graphs.AddPosition,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        unit_graph = await uow.repositories.unit_graphs.get(unit_id=cmd.unit_id)
        if not unit_graph:
            raise ValueError("Unit graph not found")

        position = Position(
            location_id=cmd.location_id,
            layout_id=cmd.layout_id,
            coordinates=cmd.coordinates,
            start=cmd.start,
            end=cmd.end
        )
        await _validate_position_layout(uow, position)
        unit_graph.add_position(cmd.unit_id, position)
        await uow.commit()

async def _validate_position_layout(uow: AbstractUnitHolder, position: Position):
    # A position links the unit to a location and layout, so the user must be able to read them
    await uow.controls.require_access(ControlledModelLabel.LOCATION, [position.location_id], Access.READ)
    if position.layout_id:
        await uow.controls.require_access(ControlledModelLabel.LAYOUT, [position.layout_id], Access.READ)
        if not position.coordinates:
            raise ValueError("Coordinates required if a layout is specified")

        layout_tree = await uow.repositories.layout_trees.get(layout_id=position.layout_id)
        if layout_tree is None:
            raise NoResultFoundError("Layout tree with the provided layout ID was not found")
        layout = layout_tree.get_layout(position.layout_id)
        if not len(position.coordinates) == len(layout.axes):
            raise ValueError(f"Coordinates must match the length of specified layout axes")

        if not layout_tree.get_location(layout.id) == position.location_id:
            raise ValueError("Layout location does not match the position location")

        layout_type = await uow.ontology.get_entry(entry_id=layout.type, label=OntologyEntryLabel.LAYOUT_TYPE)
        if layout_type is None:
            raise NoResultFoundError("Layout type with the provided type ID was not found")
        for i, p in enumerate(position.coordinates):
            if layout_type.axes[i] in [AxisType.COORDINATE, AxisType.CARTESIAN]:
                try:
                    float(p)
                except ValueError:
                    raise ValueError("Coordinate and Cartesian positions require numeric values")

@handlers.command_handler()
async def remove_position(
        cmd: commands.unit_graphs.RemovePosition,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        unit_graph = await uow.repositories.unit_graphs.get(unit_id=cmd.unit_id)
        if not unit_graph:
            raise ValueError("Unit graph not found")
        position = Position(
            location_id=cmd.location_id,
            layout_id=cmd.layout_id,
            coordinates=cmd.coordinates,
            start=cmd.start,
            end=cmd.end
        )
        unit_graph.remove_position(unit_id=cmd.unit_id, position=position)
        await uow.commit()