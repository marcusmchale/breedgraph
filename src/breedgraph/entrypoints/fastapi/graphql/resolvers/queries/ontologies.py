from ariadne import ObjectType, UnionType, InterfaceType

from src.breedgraph.domain.model.ontology import OntologyEntryStored
from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import update_ontology_map

from typing import List

import logging

logger = logging.getLogger(__name__)

from . import graphql_query
from ..registry import graphql_resolvers

# Object types for interfaces and specific types
subject = ObjectType("Subject")
trait = ObjectType("Trait")
condition = ObjectType("Condition")
scale = ObjectType("Scale")
category = ObjectType("Category")
observation_method = ObjectType("ObservationMethod")
variable = ObjectType("Variable")
control_method = ObjectType("ControlMethod")
parameter = ObjectType("Parameter")
event = ObjectType("Event")

# Union and interface types
ontology_entry_union = UnionType("OntologyEntryUnion")
ontology_entry_interface = InterfaceType("OntologyEntryInterface")
related_to_terms = InterfaceType("RelatedToTerms")

graphql_resolvers.register_type_resolvers(
    ontology_entry_union, ontology_entry_interface, related_to_terms,
    subject, trait, condition,
    scale, category, observation_method, variable,
    control_method, parameter, event
)

# Type resolver for union
@ontology_entry_union.type_resolver
def resolve_ontology_entry_type(obj, *_):
    """Resolve the concrete type for union members"""
    if hasattr(obj, 'label'):
        return obj.label
    else:
        raise ValueError(f"Could not determine type for object: {obj}")

# Type resolver for interface
@ontology_entry_interface.type_resolver
def resolve_ontology_entry_interface_type(obj, *_):
    """Resolve the concrete type for interface members"""
    if hasattr(obj, 'label'):
        return obj.label
    else:
        raise ValueError(f"Could not determine type for object: {obj}")


@graphql_query.field("ontology_entries")
@graphql_payload
@require_authentication
async def get_ontology_entries(
        _,
        info,
        entry_ids: List[int] = None,
        names: List[str] = None,
        labels: List[str] = None,
        version: int = None  # if not provided, then current
) -> List[OntologyEntryStored]:
    await update_ontology_map(info.context, entry_ids=entry_ids, version=version)
    entries_map = info.context.get('ontology_entries')
    if names or labels:
        user_id = info.context.get('user_id')
        bus = info.context.get('bus')
        entry_ids = entry_ids or []
        async with bus.uow.get_uow(user_id=user_id) as uow:
            async for entry in uow.ontology.get_entries(names=names, labels=labels, version=version, as_output=True):
                entry_ids.append(entry.id)
                entries_map[entry.id] = entry
    return [entries_map[entry_id] for entry_id in entry_ids]

async def resolve_ontology_entries(context, entry_ids):
    await update_ontology_map(context, entry_ids=entry_ids)
    entries_map = context.get('ontology_entries')
    return [entries_map[entry_id] for entry_id in entry_ids]

# Interface resolvers - common to all ontology entries
@ontology_entry_interface.field("parents")
async def resolve_parents(obj, info):
    return await resolve_ontology_entries(info.context, entry_ids=obj.parents)


@ontology_entry_interface.field("children")
async def resolve_children(obj, info):
    return await resolve_ontology_entries(info.context, entry_ids=obj.children)

@ontology_entry_interface.field("authors")
async def resolve_authors(obj, info):
    raise NotImplementedError

@ontology_entry_interface.field("references")
def resolve_references(obj, info):
    raise NotImplementedError

# RelatedToTerms interface resolver
@related_to_terms.field("terms")
async def resolve_terms(obj, info):
    return await resolve_ontology_entries(info.context, entry_ids=obj.terms)

# Subject-specific resolvers
@subject.field("traits")
async def resolve_subject_traits(obj, info):
    return await resolve_ontology_entries(info.context, entry_ids=obj.traits)

@subject.field("conditions")
async def resolve_subject_conditions(obj, info):
    return await resolve_ontology_entries(info.context, entry_ids=obj.conditions)

# Trait-specific resolvers
@trait.field("subjects")
async def resolve_trait_subjects(obj, info):
    return await resolve_ontology_entries(info.context, entry_ids=obj.subjects)

@trait.field("variables")
async def resolve_trait_variables(obj, info):
    return await resolve_ontology_entries(info.context, entry_ids=obj.variables)

# Condition-specific resolvers
@condition.field("subjects")
async def resolve_condition_subjects(obj, info):
    return await resolve_ontology_entries(info.context, entry_ids=obj.subjects)

@condition.field("parameters")
async def resolve_condition_parameters(obj, info):
    return await resolve_ontology_entries(info.context, entry_ids=obj.parameters)

# Scale-specific resolvers
@scale.field("categories")
async def resolve_scale_categories(obj, info):
    return await resolve_ontology_entries(info.context, entry_ids=obj.categories)

@scale.field("variables")
async def resolve_scale_variables(obj, info):
    return await resolve_ontology_entries(info.context, entry_ids=obj.variables)

@scale.field("parameters")
async def resolve_scale_parameters(obj, info):
    return await resolve_ontology_entries(info.context, entry_ids=obj.parameters)

# Category-specific resolvers
@category.field("scales")
async def resolve_category_scales(obj, info):
    return await resolve_ontology_entries(info.context, entry_ids=obj.scales)

# ObservationMethod-specific resolvers
@observation_method.field("variables")
async def resolve_observation_method_variables(obj, info):
    return await resolve_ontology_entries(info.context, entry_ids=obj.variables)

# Variable-specific resolvers
@variable.field("trait")
async def resolve_variable_trait(obj, info):
    entries = await resolve_ontology_entries(info.context, entry_ids=[obj.trait])
    return entries[0]

@variable.field("observationMethod")
async def resolve_variable_method(obj, info):
    entries = await resolve_ontology_entries(info.context, entry_ids=[obj.observation_method])
    return entries[0]

@variable.field("scale")
async def resolve_variable_scale(obj, info):
    entries = await resolve_ontology_entries(info.context, entry_ids=[obj.scale])
    return entries[0]

# ControlMethod-specific resolvers
@control_method.field("parameters")
async def resolve_control_method_parameters(obj, info):
    return await resolve_ontology_entries(info.context, entry_ids=[obj.parameters])

# Parameter-specific resolvers
@parameter.field("condition")
async def resolve_parameter_condition(obj, info):
    entries = await resolve_ontology_entries(info.context, entry_ids=[obj.condition])
    return entries[0]

@parameter.field("controlMethod")
async def resolve_parameter_control_method(obj, info):
    entries = await resolve_ontology_entries(info.context, entry_ids=[obj.control_method])
    return entries[0]

@parameter.field("scale")
async def resolve_parameter_scale(obj, info):
    entries = await resolve_ontology_entries(info.context, entry_ids=[obj.scale])
    return entries[0]

# Event-specific resolvers
@event.field("variables")
async def resolve_event_variables(obj, info):
    return await resolve_ontology_entries(info.context, entry_ids=[obj.variables])

@event.field("parameters")
async def resolve_event_parameters(obj, info):
    return await resolve_ontology_entries(info.context, entry_ids=[obj.parameters])
