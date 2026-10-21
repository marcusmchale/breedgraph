from breedgraph.custom_exceptions import NoResultFoundError, IllegalOperationError
from breedgraph.service_layer.infrastructure import AbstractUnitOfWorkFactory, AbstractUnitHolder
from breedgraph.domain import commands
from breedgraph.domain.model.unit_graphs import UnitInput, Position, UnitGraph
from breedgraph.domain.model.ontology import AxisType, OntologyEntryLabel, LayoutTypeStored
from breedgraph.domain.model.controls import Access, ControlledModelLabel
from breedgraph.domain.services.unit_positions import validate_position
from breedgraph.service_layer.application.unit_positions import ArrivalSelection

from typing import List


from ..registry import handlers

import logging
logger = logging.getLogger(__name__)

@handlers.command_handler()
async def create_unit(
        cmd: commands.unit_graphs.CreateUnit,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id, write_team=cmd.write_team, release=cmd.release) as uow:
        await uow.controls.require_read(ControlledModelLabel.GERMPLASM, [cmd.germplasm_id])
        unit_input = UnitInput(
            subject = cmd.subject_id,
            germplasm = cmd.germplasm_id,
            name = cmd.name,
            description = cmd.description
        )
        # written with the unit: the unit graph repository writes positions only for new units
        if cmd.location_id:
            position = Position(
                location_id=cmd.location_id,
                layout_id=cmd.layout_id,
                coordinates=cmd.coordinates,
                start=cmd.start,
                end=cmd.end
            )
            validate_position(position)
            await _validate_position_layout(uow, position)
            unit_input.positions.append(position)
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

        await uow.commit()

@handlers.command_handler()
async def update_unit(
        cmd: commands.unit_graphs.UpdateUnit,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        unit_graph = await uow.repositories.unit_graphs.get(unit_id=cmd.unit_id)
        if unit_graph is None:
            raise NoResultFoundError("Unit not found")
        unit = unit_graph.get_unit(cmd.unit_id)

        # Update unit fields if provided; given as None, the subject and germplasm are removed
        if 'subject_id' in cmd.model_fields_set:
            unit.subject = cmd.subject_id
        if 'germplasm_id' in cmd.model_fields_set:
            if cmd.germplasm_id != unit.germplasm:
                await uow.controls.require_read(ControlledModelLabel.GERMPLASM, [cmd.germplasm_id])
            unit.germplasm = cmd.germplasm_id
        if cmd.name is not None:
            unit.name = cmd.name
        if cmd.description is not None:
            unit.description = cmd.description

        # Handle parent/child relationships if provided, children first as we may split unit graphs after
        if cmd.children is not None:
            await _change_children(uow, unit_graph, cmd.unit_id, cmd.children)

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
                if new_unit_graph is None:
                    raise NoResultFoundError("Parent unit not found")
                new_unit_graph.merge_unit_graph(unit_graph, parents=cmd.parents)

        await uow.commit()

@handlers.command_handler()
async def delete_unit(
        cmd: commands.unit_graphs.DeleteUnit,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        unit_graph = await uow.repositories.unit_graphs.get(unit_id=cmd.unit_id)
        if unit_graph is None:
            raise NoResultFoundError("Unit not found")
        unit_graph.remove_unit(cmd.unit_id)
        await uow.commit()

async def _change_children(uow: AbstractUnitHolder, unit_graph: UnitGraph, unit_id: int, children: List[int]):
    """
    Make children the unit's children. A child that only this unit holds leaves as the root of a unit graph of its own
    (a split, as removing a unit's parents is), and a child from another unit graph must be its root, which is merged
    in below the unit (as on creation).
    """
    current = set(unit_graph.get_children_ids(unit_id))
    wanted = set(children)
    splitting = {child_id for child_id in current - wanted if set(unit_graph.get_parent_ids(child_id)) == {unit_id}}
    for child_id in splitting:
        await uow.controls.require_access(ControlledModelLabel.UNIT, [child_id], Access.CURATE)
        await uow.controls.require_access(ControlledModelLabel.UNIT, [unit_id], Access.READ)
        await uow.restructuring.split_unit_graph(unit_graph, child_id)
    for child_id in wanted - current:
        if unit_graph.has_unit(child_id):
            continue
        child_unit_graph = await uow.repositories.unit_graphs.get(unit_id=child_id)
        if not child_unit_graph:
            raise ValueError("Child unit graph not found")
        if not child_unit_graph.get_root_id() == child_id:
            raise ValueError("Merging unit graphs requires all children to be the root of their respective unit graph")
        unit_graph.merge_unit_graph(unit_graph=child_unit_graph, parents=[unit_id])
    # the split children keep their edges here: the split removed them in the database
    unit_graph.change_children(unit_id, wanted | splitting)

@handlers.command_handler()
async def add_position(
        cmd: commands.unit_graphs.AddPosition,
        uow_factory: AbstractUnitOfWorkFactory
):
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        position = Position(
            location_id=cmd.location_id,
            layout_id=cmd.layout_id,
            coordinates=cmd.coordinates,
            start=cmd.start,
            end=cmd.end
        )
        validate_position(position)
        await _validate_position_layout(uow, position)
        await uow.positions.add_position(cmd.unit_id, position)
        await uow.commit()

@handlers.command_handler()
async def move_units(
        cmd: commands.unit_graphs.MoveUnits,
        uow_factory: AbstractUnitOfWorkFactory
) -> List[int]:
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        unit_ids = await _selected_unit_ids(uow, cmd.units)
        position = Position(
            location_id=cmd.location_id,
            layout_id=cmd.layout_id,
            coordinates=cmd.coordinates,
            start=cmd.start,
            end=cmd.end
        )
        validate_position(position)
        # one destination for them all, validated once
        await _validate_position_layout(uow, position)
        moved = await uow.positions.move_units(unit_ids, position)
        await uow.commit()
        return moved

@handlers.command_handler()
async def change_positions(
        cmd: commands.unit_graphs.ChangePositions,
        uow_factory: AbstractUnitOfWorkFactory
) -> List[int]:
    async with uow_factory.get_uow(user_id=cmd.agent_id) as uow:
        unit_ids = await _selected_unit_ids(uow, cmd.units)

        async def validate_place(position: Position):
            await _validate_position_layout(uow, position)

        changed = await uow.positions.change_positions(
            unit_ids, at=cmd.at.given(), change=cmd.change.given(), validate_place=validate_place
        )
        await uow.commit()
        return changed

async def _selected_unit_ids(uow: AbstractUnitHolder, selection: commands.unit_graphs.UnitsSelection) -> List[int]:
    arrival = selection.arrival
    return await uow.positions.selected_unit_ids(
        selection.unit_ids,
        None if arrival is None else ArrivalSelection(
            location_id=arrival.location_id, start=arrival.start, unit_id=arrival.unit_id
        )
    )

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
        position = Position(
            location_id=cmd.location_id,
            layout_id=cmd.layout_id,
            coordinates=cmd.coordinates,
            start=cmd.start,
            end=cmd.end
        )
        await uow.positions.remove_position(cmd.unit_id, position)
        await uow.commit()