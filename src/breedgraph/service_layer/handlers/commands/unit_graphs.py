from breedgraph.custom_exceptions import NoResultFoundError, IllegalOperationError, ProtectedNodeError
from breedgraph.service_layer.infrastructure import AbstractUnitOfWorkFactory, AbstractUnitHolder
from breedgraph.domain import commands
from breedgraph.domain.model.unit_graphs import UnitInput, UnitStored, Position, UnitGraph, UnitDerivation, child_name
from breedgraph.domain.model.ontology import AxisType, OntologyEntryLabel, LayoutTypeStored
from breedgraph.domain.model.controls import Access, ControlledModelLabel
from breedgraph.domain.services.unit_positions import validate_position, place_at
from breedgraph.domain.services.lineages import seen_germplasm
from breedgraph.service_layer.application.unit_positions import ArrivalSelection

from dataclasses import replace
from typing import List, Dict, Iterable, Set, Tuple


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
        if cmd.subject_id is not None:
            await uow.ontology.require_entries([cmd.subject_id], label=OntologyEntryLabel.SUBJECT)
        unit_input = UnitInput(
            subject = cmd.subject_id,
            germplasm = cmd.germplasm_id,
            name = cmd.name,
            description = cmd.description,
            derived_from = list(cmd.derived_from or [])
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

        await _check_derived_from(uow, unit_graph, unit_id, unit_input.derived_from, [])
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
            if cmd.subject_id is not None and cmd.subject_id != unit.subject:
                await uow.ontology.require_entries([cmd.subject_id], label=OntologyEntryLabel.SUBJECT)
            unit.subject = cmd.subject_id
        if 'germplasm_id' in cmd.model_fields_set:
            if cmd.germplasm_id != unit.germplasm:
                await uow.controls.require_read(ControlledModelLabel.GERMPLASM, [cmd.germplasm_id])
            unit.germplasm = cmd.germplasm_id
        if cmd.given('name'):
            unit.name = cmd.given_text('name')
        if cmd.given('description'):
            unit.description = cmd.given_text('description')
        if cmd.derived_from is not None:
            await _check_derived_from(uow, unit_graph, cmd.unit_id, cmd.derived_from, unit.derived_from)
            unit.derived_from = list(cmd.derived_from)

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
        # what refers to the unit keeps it: germplasm that came from it (as units keep their germplasm), units derived
        # from it, and records for it, which would be left without a unit. Checked after the access needed to remove
        # it, so only those who could remove the unit learn of germplasm, units or records they may not see
        await uow.controls.require_access(ControlledModelLabel.UNIT, [cmd.unit_id], Access.CURATE)
        if await uow.guards.germplasm_from_unit(cmd.unit_id):
            raise ProtectedNodeError("Germplasm came from this unit, so it may not be deleted.")
        if await uow.guards.unit_has_derivatives(cmd.unit_id):
            raise ProtectedNodeError("Units are derived from this unit, so it may not be deleted.")
        if await uow.guards.unit_has_records(cmd.unit_id):
            raise ProtectedNodeError("Records are for this unit, so it may not be deleted: remove them first.")
        unit_graph.remove_unit(cmd.unit_id)
        await uow.commit()

async def _check_derived_from(
        uow: AbstractUnitHolder,
        unit_graph: UnitGraph,
        unit_id: int,
        derived_from: List[UnitDerivation],
        current: List[UnitDerivation]
):
    """
    The units a unit is derived from, as given: each once, and those not already among them readable, outside the
    unit's context (UnitGraph.check_derived_from) and not derived from it, so derivations stay acyclic. A unit it stays
    derived from may since have been hidden from the user.
    """
    source_ids = [derivation.unit_id for derivation in derived_from]
    if len(set(source_ids)) != len(source_ids):
        raise ValueError("A unit is derived from each unit once")
    added = set(source_ids) - {derivation.unit_id for derivation in current}
    if not added:
        return
    await uow.controls.require_read(ControlledModelLabel.UNIT, added)
    unit_graph.check_derived_from(unit_id, added)
    if await uow.guards.derivation_cycle(unit_id, list(added)):
        raise IllegalOperationError("A unit can't be derived from a unit derived from it")

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

@handlers.command_handler()
async def derive_units(
        cmd: commands.unit_graphs.DeriveUnits,
        uow_factory: AbstractUnitOfWorkFactory
) -> List[int]:
    async with uow_factory.get_uow(user_id=cmd.agent_id, write_team=cmd.write_team, release=cmd.release) as uow:
        source_ids = await _selected_unit_ids(uow, cmd.units)
        await uow.controls.require_read(ControlledModelLabel.UNIT, source_ids)
        await uow.controls.require_read(ControlledModelLabel.GERMPLASM, [cmd.germplasm_id])
        # the germplasm given, else each source's copied, or none
        copying = cmd.germplasm_id is None and cmd.copy_germplasm
        sources = await _units_as_seen(uow, source_ids, with_germplasm=copying)
        # the subject given, else each source's copied: either way the new units' subjects are of the current ontology
        subject_ids = {cmd.subject_id} if cmd.subject_id is not None else {source.subject for source, _ in sources.values()}
        await uow.ontology.require_entries([s for s in subject_ids if s is not None], label=OntologyEntryLabel.SUBJECT)

        position = None
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
        elif not cmd.parents:
            raise ValueError("Derived units need parents, or a position to be the roots of unit graphs of their own")

        unit_graph = None
        if cmd.parents:
            unit_graph = await uow.repositories.unit_graphs.get(unit_id=cmd.parents[0])
            if unit_graph is None:
                raise NoResultFoundError("Parent unit not found")
            existing = set(unit_graph.entries)

        derived = {}
        for source_id in source_ids:
            source, germplasm = sources[source_id]
            unit_input = UnitInput(
                subject=cmd.subject_id if cmd.subject_id is not None else source.subject,
                germplasm=germplasm if copying else cmd.germplasm_id,
                name=source.name,
                positions=[replace(position)] if position else [],
                derived_from=[UnitDerivation(unit_id=source_id, stage=cmd.stage, description=cmd.description)]
            )
            if unit_graph is not None:
                unit_id = unit_graph.add_unit(unit_input, parents=cmd.parents)
                unit_graph.check_derived_from(unit_id, [source_id])
            else:
                derived[source_id] = (await uow.repositories.unit_graphs.create(unit_input)).get_root_id()

        await uow.commit()
        if unit_graph is not None:
            # stored on commit: each new unit is known by the unit it came from
            derived = {
                unit.derived_from[0].unit_id: unit_id
                for unit_id, unit in unit_graph.entries.items() if unit_id not in existing
            }
        return [derived[source_id] for source_id in source_ids]

# children added to each unit at once, at most
MAX_CHILDREN = 100

@handlers.command_handler()
async def add_children(
        cmd: commands.unit_graphs.AddChildren,
        uow_factory: AbstractUnitOfWorkFactory
) -> List[int]:
    if not 1 <= cmd.count <= MAX_CHILDREN:
        raise ValueError(f"Add from 1 to {MAX_CHILDREN} children to each unit")
    template = (cmd.name or '').strip() or None
    if template is not None and cmd.count > 1 and '{n}' not in template:
        raise ValueError("With more than one child to each unit, the name needs {n} to tell them apart")
    async with uow_factory.get_uow(user_id=cmd.agent_id, write_team=cmd.write_team, release=cmd.release) as uow:
        parent_ids = await _selected_unit_ids(uow, cmd.parents)
        await uow.controls.require_read(ControlledModelLabel.UNIT, parent_ids)
        await uow.controls.require_read(ControlledModelLabel.GERMPLASM, [cmd.germplasm_id])
        await uow.ontology.require_entries([cmd.subject_id], label=OntologyEntryLabel.SUBJECT)
        subject = await uow.ontology.get_entry(entry_id=cmd.subject_id, label=OntologyEntryLabel.SUBJECT)

        # the unit graph of each parent, which its children join
        graphs: Dict[int, UnitGraph] = {}
        async for unit_graph in uow.repositories.unit_graphs.get_all(unit_ids=parent_ids):
            for parent_id in parent_ids:
                if unit_graph.has_unit(parent_id):
                    graphs[parent_id] = unit_graph
        missing = [str(parent_id) for parent_id in parent_ids if parent_id not in graphs]
        if missing:
            raise NoResultFoundError(f"Unit {', '.join(missing[:10])} was not found")
        names = await _unit_names(uow, graphs, parent_ids)

        places = {}
        if cmd.start is not None:
            places = await _places_at(uow, graphs, parent_ids, cmd.start, names)
            # validated once for each place, as the children of a field's trees share theirs
            for position in {(p.location_id, p.layout_id, tuple(p.coordinates or [])): p for p in places.values()}.values():
                await _validate_position_layout(uow, position)

        existing = {graph.get_root_id(): set(graph.entries) for graph in graphs.values()}
        for parent_id in parent_ids:
            for n in range(1, cmd.count + 1):
                unit_input = UnitInput(
                    subject=cmd.subject_id,
                    germplasm=cmd.germplasm_id,
                    name=None if template is None else child_name(template, names[parent_id], subject.name, n),
                    description=cmd.description,
                    positions=[replace(places[parent_id], start=cmd.start)] if cmd.start is not None else []
                )
                graphs[parent_id].add_unit(unit_input, parents=[parent_id])

        await uow.commit()
        # stored on commit: each child known by its parent
        children = {parent_id: [] for parent_id in parent_ids}
        for graph in {graph.get_root_id(): graph for graph in graphs.values()}.values():
            for unit_id in sorted(set(graph.entries) - existing[graph.get_root_id()]):
                children[graph.get_parent_ids(unit_id)[0]].append(unit_id)
        return [child_id for parent_id in parent_ids for child_id in children[parent_id]]

async def _unit_names(uow: AbstractUnitHolder, graphs: Dict[int, UnitGraph], unit_ids: List[int]) -> Dict[int, str]:
    """Each unit's name, or for one without a name its subject and id, as the Units pages show it"""
    units = {unit_id: graphs[unit_id].get_unit(unit_id) for unit_id in unit_ids}
    subjects = {}
    for subject_id in {unit.subject for unit in units.values() if not unit.name and unit.subject is not None}:
        entry = await uow.ontology.get_cited_entry(subject_id, label=OntologyEntryLabel.SUBJECT)
        subjects[subject_id] = entry.name if entry is not None else 'Unit'
    return {
        unit_id: unit.name or f"{subjects.get(unit.subject, 'Unit')} {unit_id}"
        for unit_id, unit in units.items()
    }

async def _places_at(
        uow: AbstractUnitHolder,
        graphs: Dict[int, UnitGraph],
        unit_ids: List[int],
        time,
        names: Dict[int, str]
) -> Dict[int, Position]:
    """Where each unit is at the time, as the user sees it (place_at); refused for those whose place can't be told"""
    above = {u for unit_id in unit_ids for u in graphs[unit_id].get_ancestors(unit_id)}
    readable = await _readable(uow, ControlledModelLabel.UNIT, above | set(unit_ids))
    places, unplaced = {}, []
    for unit_id in unit_ids:
        graph = graphs[unit_id]
        place = place_at(
            unit_id,
            time,
            positions_of=lambda u, graph=graph: graph.get_unit(u).positions,
            parents_of=graph.get_parent_ids,
            hidden=lambda u: u not in readable
        )
        if place is None:
            unplaced.append(names[unit_id])
        else:
            places[unit_id] = place
    if unplaced:
        listed = ', '.join(sorted(unplaced, key=str.casefold)[:5])
        more = f" and {len(unplaced) - 5} more" if len(unplaced) > 5 else ''
        raise ValueError(
            f"Where {listed}{more} {'was' if len(unplaced) == 1 else 'were'} at {time} can't be told, "
            f"so their children can't be placed there: add them without a start, to be where their parents are"
        )
    return places

async def _units_as_seen(
        uow: AbstractUnitHolder, unit_ids: List[int], with_germplasm: bool = True
) -> Dict[int, Tuple[UnitStored, int | None]]:
    """
    Each of the units the user reads, with the germplasm it has or takes from the units above it as the user sees it
    (Unit.inheritedGermplasm), where they can read that germplasm; with_germplasm false, none
    """
    found = {}
    async for unit_graph in uow.repositories.unit_graphs.get_all(unit_ids=unit_ids):
        redacted = await uow.repositories.unit_graphs.redacted(unit_graph)
        for unit_id in unit_ids:
            if redacted.has_unit(unit_id):
                germplasm = seen_germplasm(unit_graph, redacted, unit_id) if with_germplasm else None
                found[unit_id] = (redacted.get_unit(unit_id), germplasm)
    readable = await _readable(
        uow, ControlledModelLabel.GERMPLASM, {germplasm for _, germplasm in found.values() if germplasm is not None}
    )
    return {unit_id: (unit, germplasm if germplasm in readable else None) for unit_id, (unit, germplasm) in found.items()}

async def _readable(uow: AbstractUnitHolder, label: ControlledModelLabel, model_ids: Iterable[int]) -> Set[int]:
    model_ids = list(model_ids)
    if not model_ids:
        return set()
    controllers = await uow.controls.get_controllers(label, model_ids)
    return {
        model_id for model_id, controller in controllers.items()
        if controller.has_access(Access.READ, uow.controls.user_id, uow.controls.access_teams[Access.READ])
    }

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

        # the type of an existing layout, as cited, so units can still be placed in a layout of a removed type
        layout_type = await uow.ontology.get_cited_entry(layout.type, label=OntologyEntryLabel.LAYOUT_TYPE)
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