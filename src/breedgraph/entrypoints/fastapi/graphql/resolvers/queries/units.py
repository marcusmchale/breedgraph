from ariadne import ObjectType

from breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload
from breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import (
    _get_lock,
    get_context_lock,
    get_context_views,
    update_units_map,
    update_ontology_map,
    update_locations_map,
    update_layouts_map,
    update_germplasm_map
)

from breedgraph.domain.model.unit_graphs import UnitOutput, UnitArrival, arrival_key
from breedgraph.service_layer.queries.read_models import OntologyViewMode

from typing import List

import asyncio

import logging
logger = logging.getLogger(__name__)

from . import graphql_query
from ..registry import graphql_resolvers
unit = ObjectType("Unit")
position = ObjectType("Position")
subject_units = ObjectType("SubjectUnits")
unit_arrival = ObjectType("UnitArrival")
graphql_resolvers.register_type_resolvers(unit, position, subject_units, unit_arrival)

ARRIVAL_UNITS_LIMIT = 1000

@graphql_query.field("unitsRoots")
@graphql_payload
async def get_unit_graphs(_, info, location_ids: List[int]|None = None) -> List[UnitOutput]:
    return await update_units_map(info.context, location_ids=location_ids or [])

@graphql_query.field("unitsArrivals")
@graphql_payload
async def get_unit_arrivals(_, info, location_ids: List[int], unit_id: int | None = None) -> List[UnitArrival]:
    async with get_context_lock(info.context):
        views = await get_context_views(info.context)
        arrivals = await views.units.get_arrivals(location_ids=location_ids, unit_id=unit_id)
    # their units by subject are read for every arrival of the request at once (UnitArrival.unitsBySubject)
    info.context.setdefault('unit_arrivals', []).extend(arrivals)
    return arrivals

@graphql_query.field("unitsArrivalUnits")
@graphql_payload
async def get_arrival_units(_, info, arrival: dict, offset: int | None = None, limit: int | None = None) -> List[UnitOutput]:
    limit = min(100 if limit is None else limit, ARRIVAL_UNITS_LIMIT)
    unit_id = arrival.get('unit_id')
    async with get_context_lock(info.context):
        views = await get_context_views(info.context)
        units = await views.units.get_arrival_units(
            location_id=int(arrival['location_id']),
            start=arrival.get('start'),
            unit_id=int(unit_id) if unit_id is not None else None,
            offset=offset or 0,
            limit=limit
        )
    info.context.setdefault('units_map', dict()).update({u.id: u for u in units})
    return units

@unit_arrival.field("location")
async def resolve_arrival_location(obj: UnitArrival, info):
    await update_locations_map(info.context, location_ids=[obj.location_id])
    return info.context.get('locations_map').get(obj.location_id)

@unit_arrival.field("roots")
async def resolve_arrival_roots(obj: UnitArrival, info):
    await update_units_map(info.context, unit_ids=obj.root_ids)
    units_map = info.context.get('units_map')
    return [units_map[i] for i in obj.root_ids if i in units_map]

@unit_arrival.field("unitsBySubject")
async def resolve_arrival_units_by_subject(obj: UnitArrival, info):
    """Read once for every arrival of the request, as a picker lists all those at the locations it was given"""
    key = arrival_key(obj.location_id, obj.start)
    async with _get_lock(info.context, '_arrival_units_lock'):
        by_arrival = info.context.setdefault('arrival_units_by_subject', {})
        if key not in by_arrival:
            pending = {
                arrival_key(a.location_id, a.start): (a.location_id, a.start)
                for a in [obj, *info.context.get('unit_arrivals', [])]
            }
            pending = [arrival for k, arrival in pending.items() if k not in by_arrival]
            async with get_context_lock(info.context):
                views = await get_context_views(info.context)
                by_arrival.update(await views.units.get_arrival_units_by_subject(pending))
    return [{'subject': subject, 'units': units} for subject, units in by_arrival.get(key, {}).items()]

@graphql_query.field("unitsUnits")
@graphql_payload
async def get_units(_, info, ids: List[int]) -> List[UnitOutput]:
    await update_units_map(info.context, unit_ids=ids)
    units_map = info.context.get('units_map')
    # an id of no unit (one deleted while a page still shows it) is left out, not a null failing the whole result
    return [units_map[i] for i in ids if i in units_map]

@graphql_query.field("unitsDescendantsBySubject")
@graphql_payload
async def get_descendants_by_subject(_, info, unit_ids: List[int]) -> List[dict]:
    bus = info.context.get('bus')
    async with bus.views_factory.get_views(user_id=info.context.get('user_id')) as views:
        by_subject = await views.units.get_descendants_by_subject(unit_ids=unit_ids)
    return [{'subject': subject, 'units': units} for subject, units in by_subject.items()]

@subject_units.field("subject")
async def resolve_subject_units_subject(obj, info):
    if obj.get('subject') is None:
        return None
    await update_ontology_map(info.context, entry_ids=[obj['subject']], view=OntologyViewMode.REFERENTIAL)
    return info.context.get('ontology_map').get(obj['subject'])

@unit.field("subject")
async def resolve_subject(obj, info):
    await update_ontology_map(info.context, entry_ids=[obj.subject], view=OntologyViewMode.REFERENTIAL)
    ontology_map = info.context.get('ontology_map')
    return ontology_map.get(obj.subject)

@unit.field("germplasm")
def resolve_germplasm(obj, info):
    # synchronous when already mapped (as for records' units, preloaded per page): an async resolver costs a task per unit
    germplasm_map = info.context.get('germplasm_map', {})
    if obj.germplasm is None or obj.germplasm in germplasm_map:
        return germplasm_map.get(obj.germplasm)
    return _load_germplasm(info, obj.germplasm)

async def _load_germplasm(info, entry_id):
    await update_germplasm_map(info.context, entry_ids=[entry_id])
    return info.context.get('germplasm_map').get(entry_id)

@unit.field("parents")
async def resolve_parents(obj, info):
    await update_units_map(info.context, unit_ids=obj.parents)
    units_map = info.context.get('units_map')
    return [units_map.get(i) for i in obj.parents]

@unit.field("ancestors")
async def resolve_ancestors(obj, info):
    """
    Read once for every unit of the request so far: the units a page asks for share most of their ancestors, and one
    query per unit would be slow. The ancestors themselves are then read in one call.
    """
    async with _get_lock(info.context, '_unit_ancestors_lock'):
        ancestors_map = info.context.setdefault('unit_ancestors', {})
        if obj.id not in ancestors_map:
            pending = [obj.id] + [i for i in info.context.get('units_map', {}) if i not in ancestors_map and i != obj.id]
            async with get_context_lock(info.context):
                views = await get_context_views(info.context)
                ancestors_map.update(await views.units.get_ancestor_ids(pending))
            await update_units_map(info.context, unit_ids={a for i in pending for a in ancestors_map.get(i, [])})
    units_map = info.context.get('units_map', {})
    return [units_map[i] for i in ancestors_map.get(obj.id, []) if i in units_map]

@unit.field("inheritedGermplasm")
async def resolve_inherited_germplasm(obj, info):
    """
    Read in one batch for the units of the request that ask for it: each joins the batch and yields once, so the other
    units of its list join before the first of them reads it. Not for every unit loaded, as ancestors are: a unit
    graph's root loads its children, often thousands, that ask for nothing more than their names.
    """
    if obj.germplasm is not None:
        return None
    inherited = info.context.setdefault('inherited_germplasm', {})
    if obj.id not in inherited:
        asked = info.context.setdefault('_inherited_germplasm_asked', set())
        asked.add(obj.id)
        await asyncio.sleep(0)
        async with _get_lock(info.context, '_inherited_germplasm_lock'):
            pending = [i for i in asked if i not in inherited]
            if pending:
                async with get_context_lock(info.context):
                    views = await get_context_views(info.context)
                    found = await views.units.get_inherited_germplasm(pending)
                inherited.update({i: found.get(i) for i in pending})
                asked.difference_update(pending)
    value = inherited.get(obj.id)
    if value is None:
        return None
    germplasm_id, unit_id = value
    await update_germplasm_map(info.context, entry_ids=[germplasm_id])
    await update_units_map(info.context, unit_ids=[unit_id])
    return {
        'germplasm': info.context.get('germplasm_map', {}).get(germplasm_id),
        'unit': info.context.get('units_map', {}).get(unit_id)
    }

def _derivation(derivation, units_map) -> dict:
    return {
        'unit': units_map.get(derivation.unit_id),
        'source_type': derivation.source_type.value,
        'description': derivation.description
    }

@unit.field("derivedFrom")
async def resolve_derived_from(obj, info):
    await update_units_map(info.context, unit_ids=[derivation.unit_id for derivation in obj.derived_from])
    units_map = info.context.get('units_map', {})
    return [_derivation(derivation, units_map) for derivation in obj.derived_from if derivation.unit_id in units_map]

@unit.field("derivatives")
async def resolve_derivatives(obj, info):
    """Read in one batch for the units of the request that ask for it, as inheritedGermplasm is"""
    derivatives = info.context.setdefault('unit_derivatives', {})
    if obj.id not in derivatives:
        asked = info.context.setdefault('_unit_derivatives_asked', set())
        asked.add(obj.id)
        await asyncio.sleep(0)
        async with _get_lock(info.context, '_unit_derivatives_lock'):
            pending = [i for i in asked if i not in derivatives]
            if pending:
                async with get_context_lock(info.context):
                    views = await get_context_views(info.context)
                    derivatives.update(await views.units.get_derivatives(pending))
                asked.difference_update(pending)
    found = derivatives.get(obj.id, [])
    await update_units_map(info.context, unit_ids=[derivation.unit_id for derivation in found])
    units_map = info.context.get('units_map', {})
    return [_derivation(derivation, units_map) for derivation in found if derivation.unit_id in units_map]

@unit.field("children")
async def resolve_children(obj, info):
    await update_units_map(info.context, unit_ids=obj.children)
    units_map = info.context.get('units_map')
    return [units_map.get(i) for i in obj.children]

@position.field("location")
async def resolve_location(obj, info):
    await update_locations_map(info.context, location_ids=[obj.location_id])
    locations_map = info.context.get('locations_map')
    return locations_map.get(obj.location_id)

@position.field("layout")
async def resolve_layout(obj, info):
    if obj.layout_id is None:
        return None
    await update_layouts_map(info.context, layout_ids=[obj.layout_id])
    layouts_map = info.context.get('layouts_map')
    return layouts_map.get(obj.layout_id)

