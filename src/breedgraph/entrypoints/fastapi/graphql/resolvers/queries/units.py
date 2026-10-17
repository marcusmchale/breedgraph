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

from breedgraph.domain.model.unit_graphs import UnitOutput
from breedgraph.service_layer.queries.read_models import OntologyViewMode

from typing import List

import logging
logger = logging.getLogger(__name__)

from . import graphql_query
from ..registry import graphql_resolvers
unit = ObjectType("Unit")
position = ObjectType("Position")
subject_units = ObjectType("SubjectUnits")
graphql_resolvers.register_type_resolvers(unit, position, subject_units)

@graphql_query.field("unitsRoots")
@graphql_payload
async def get_unit_graphs(_, info, location_ids: List[int]|None = None) -> List[UnitOutput]:
    await update_units_map(info.context, location_ids=location_ids)
    units_map = info.context.get('units_map')
    unit_graph_roots = info.context.get('unit_graph_roots')
    return [units_map.get(i) for i in unit_graph_roots]

@graphql_query.field("unitsUnits")
@graphql_payload
async def get_units(_, info, ids: List[int]) -> List[UnitOutput]:
    await update_units_map(info.context, unit_ids=ids)
    units_map = info.context.get('units_map')
    return [units_map.get(i) for i in ids]

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

