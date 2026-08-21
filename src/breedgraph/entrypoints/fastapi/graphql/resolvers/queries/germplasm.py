from ariadne import ObjectType

from breedgraph.domain.model import LocationOutput
from breedgraph.service_layer.queries.read_models.germplasm import GermplasmEntryOutput

from breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import (
    update_germplasm_map, update_locations_map, update_ontology_map, update_reference_map
)

from typing import List

import logging

from breedgraph.service_layer.queries.read_models import OntologyViewMode

logger = logging.getLogger(__name__)

from . import graphql_query
from ..registry import graphql_resolvers

germplasm_entry = ObjectType("GermplasmEntry")
germplasm_relationship = ObjectType("GermplasmRelationship")

graphql_resolvers.register_type_resolvers(germplasm_entry, germplasm_relationship)


class GermplasmEntryRef:
    def __init__(self, id_: int):
        self.id = id_

    async def get(self, info):
        await update_germplasm_map(info.context, [self.id])
        return info.context["germplasm_map"][self.id]


@graphql_query.field("germplasmEntries")
@graphql_payload
@require_authentication
async def get_germplasm_entries(
        _,
        info,
        ids: List[int]|None = None
) -> List[GermplasmEntryOutput]:
    await update_germplasm_map(info.context, entry_ids=ids)
    germplasm_map = info.context.get('germplasm_map')
    if ids is not None:
        return [germplasm_map[i] for i in ids if i in germplasm_map]
    else:
        return [value for key, value in germplasm_map.items()]

@graphql_query.field("germplasmCrops")
@graphql_payload
@require_authentication
async def get_germplasm_crops(
        _,
        info
) -> List[GermplasmEntryOutput]:
    bus = info.context.get('bus')
    user_id = info.context.get('user_id')
    async with bus.views_factory.get_views(user_id=user_id) as views:
        return await views.germplasm.get_crops()


@germplasm_relationship.field("source")
def resolve_source_entry(obj, info):
    return GermplasmEntryRef(obj.source_id)

@germplasm_relationship.field("sink")
def resolve_sink_entry(obj, info):
    return GermplasmEntryRef(obj.sink_id)

@germplasm_entry.field("id")
def resolve_germplasm_id(obj: GermplasmEntryOutput|GermplasmEntryRef, _):
    if isinstance(obj, int):
        return obj

    return obj.id

@germplasm_entry.field("name")
async def resolve_name(obj, info):
    if isinstance(obj, GermplasmEntryRef):
        obj = await obj.get(info)

    return obj.name

@germplasm_entry.field("description")
async def resolve_description(obj, info):
    if isinstance(obj, GermplasmEntryRef):
        obj = await obj.get(info)

    return obj.description

@germplasm_entry.field("synonyms")
async def resolve_synonyms(obj, info):
    if isinstance(obj, GermplasmEntryRef):
        obj = await obj.get(info)

    return obj.synonyms

@germplasm_entry.field("time")
async def resolve_time(obj, info):
    if isinstance(obj, GermplasmEntryRef):
        obj = await obj.get(info)

    return obj.time

@germplasm_entry.field("reproduction")
async def resolve_reproduction(obj, info):
    if isinstance(obj, GermplasmEntryRef):
        obj = await obj.get(info)

    return obj.reproduction

@germplasm_entry.field("authors")
async def resolve_authors(obj, info):
    # todo Person not yet implemented
    return []



"""
    id: ID!
    name: String!
    description: String
    synonyms: [String!]
    time: DateTime
    reproduction: Reproduction
    origin: Location
    controlMethods: [ControlMethod!]
    authors: [Person!]
    references: [ReferenceInterface!]
    sources: [GermplasmRelationship!]
    sinks: [GermplasmRelationship!]
"""



@germplasm_entry.field("controlMethods")
async def resolve_germplasm_control_methods(obj: GermplasmEntryOutput|GermplasmEntryRef, info):
    if isinstance(obj, GermplasmEntryRef):
        obj = await obj.get(info)

    if not obj.control_methods:
        return None

    await update_ontology_map(
        info.context,
        entry_ids=obj.control_methods,
        view=OntologyViewMode.REFERENTIAL
    )

    ontology_map = info.context.get('ontology_map')
    return [ontology_map[i] for i in obj.control_methods]

@germplasm_entry.field("origin")
async def resolve_germplasm_origin(obj: GermplasmEntryOutput|GermplasmEntryRef, info):
    if isinstance(obj, GermplasmEntryRef):
        obj = await obj.get(info)

    if obj.origin is None:
        return None
    await update_locations_map(info.context, location_ids=[obj.origin])
    locations_map = info.context.get('locations_map')
    location = locations_map.get(obj.origin)
    if location is None:
        return LocationOutput(id=obj.origin, name='REDACTED')
    return location

@germplasm_entry.field("references")
async def resolve_germplasm_references(obj: GermplasmEntryOutput, info):
    if isinstance(obj, GermplasmEntryRef):
        obj = await obj.get(info)

    if not obj.references:
        return None
    await update_reference_map(info.context, reference_ids=obj.references)
    reference_map = info.context.get('reference_map')
    return [reference_map[i] for i in obj.references]
