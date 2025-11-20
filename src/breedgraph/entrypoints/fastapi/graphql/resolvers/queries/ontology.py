from ariadne import ObjectType, UnionType, InterfaceType

from src.breedgraph.custom_exceptions import UnauthorisedOperationError
from src.breedgraph.domain.model.ontology import (
    OntologyEntryOutput, OntologyRelationshipBase,
    OntologyEntryLabel, OntologyRelationshipLabel,
    OntologyCommit,
    Version, LifecyclePhase,
)
from src.breedgraph.domain.model.accounts import UserOutput, OntologyRole
from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import update_ontology_map, update_users_map, update_ontology_version_context

from typing import List

import logging

logger = logging.getLogger(__name__)

from . import graphql_query
from ..registry import graphql_resolvers

# Object types for interfaces and specific types
ontology_commit = ObjectType("OntologyCommit")
subject = ObjectType("Subject")
trait = ObjectType("Trait")
condition = ObjectType("Condition")
scale = ObjectType("Scale")
category = ObjectType("Category")
observation_method = ObjectType("ObservationMethod")
variable = ObjectType("Variable")
control_method = ObjectType("ControlMethod")
factor = ObjectType("Factor")
event = ObjectType("Event")

# Union and interface types
ontology_entry_union = UnionType("OntologyEntryUnion")
ontology_entry_interface = InterfaceType("OntologyEntryInterface")
related_to_terms = InterfaceType("RelatedToTerms")

graphql_resolvers.register_type_resolvers(
    ontology_commit,
    ontology_entry_union, ontology_entry_interface, related_to_terms,
    subject, trait, condition,
    scale, category,
    observation_method, variable,
    control_method, factor,
    event
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


@graphql_query.field("ontologyRelationships")
@graphql_payload
@require_authentication
async def get_ontology_relationships(
        _,
        info,
        entry_ids: List[int] = None,
        labels: List[OntologyRelationshipLabel] = None,
        phases: List[LifecyclePhase] = None,
        version_id: int = None
) -> List[OntologyRelationshipBase]:
    if version_id is None:
        version = None
    else:
        version = Version.from_packed(version_id)

    user_id = info.context.get('user_id')
    bus = info.context.get('bus')
    async with bus.uow.get_uow(user_id=user_id) as uow:
        relationships = [rel async for rel in uow.ontology.get_relationships(
                entry_ids=entry_ids,
                labels=labels,
                phases=phases,
                version=version
        )]
        return relationships


@graphql_query.field("ontologyEntries")
@graphql_payload
@require_authentication
async def get_ontology_entries(
        _,
        info,
        entry_ids: List[int] = None,
        names: List[str] = None,
        labels: List[OntologyEntryLabel] = None,
        phases: List[LifecyclePhase] = None,
        version_id: int = None  # if not provided, then current
) -> List[OntologyEntryOutput]:
    if version_id is None:
        version = None
    else:
        version = Version.from_packed(version_id)
    await update_ontology_version_context(info.context, version)
    version = info.context.get('ontology_version')
    # either get the specific entry ids requested, or get all if no filters provided.
    await update_ontology_map(
        info.context,
        entry_ids=entry_ids,
        phases=phases,
        version=version,
        names=names,
        labels=labels
    )
    ontology_map = info.context.get('ontology_map')
    return ontology_map.values()

async def resolve_ontology_entries(context, entry_ids):
    await update_ontology_map(context, entry_ids=entry_ids)
    ontology_map = context.get('ontology_map')
    return [ontology_map[entry_id] for entry_id in entry_ids]

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

@condition.field("factors")
async def resolve_condition_factors(obj, info):
    return await resolve_ontology_entries(info.context, entry_ids=obj.factors)

# Scale-specific resolvers
@scale.field("categories")
async def resolve_scale_categories(obj, info):
    return await resolve_ontology_entries(info.context, entry_ids=obj.categories)

@scale.field("variables")
async def resolve_scale_variables(obj, info):
    return await resolve_ontology_entries(info.context, entry_ids=obj.variables)

@scale.field("factors")
async def resolve_scale_factors(obj, info):
    return await resolve_ontology_entries(info.context, entry_ids=obj.factors)

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
@control_method.field("factors")
async def resolve_control_method_factors(obj, info):
    return await resolve_ontology_entries(info.context, entry_ids=obj.factors)

# Factor-specific resolvers
@factor.field("condition")
async def resolve_factor_condition(obj, info):
    entries = await resolve_ontology_entries(info.context, entry_ids=[obj.condition])
    return entries[0]

@factor.field("controlMethod")
async def resolve_factor_control_method(obj, info):
    entries = await resolve_ontology_entries(info.context, entry_ids=[obj.control_method])
    return entries[0]

@factor.field("scale")
async def resolve_factor_scale(obj, info):
    entries = await resolve_ontology_entries(info.context, entry_ids=[obj.scale])
    return entries[0]

# Event-specific resolvers
@event.field("variables")
async def resolve_event_variables(obj, info):
    return await resolve_ontology_entries(info.context, entry_ids=obj.variables)

@event.field("factors")
async def resolve_event_factors(obj, info):
    return await resolve_ontology_entries(info.context, entry_ids=obj.factors)

@graphql_query.field("ontologyCommitHistory")
@graphql_payload
@require_authentication
async def get_commit_history(
        _,
        info,
        limit = 10
) -> List[OntologyCommit]:
    context = info.context
    bus = context.get('bus')
    user_id = context.get('user_id')
    async with bus.uow.get_uow(user_id=user_id) as uow:
        history = [commit async for commit in uow.ontology.get_commit_history(limit=limit)]
        return history

@ontology_commit.field("user")
async def resolve_commit_user(obj, info):
    context = info.context
    await update_users_map(context, user_ids=[obj.user])
    users_map = context.get('users_map')
    return users_map.get(obj.user)

@graphql_query.field("ontologyRoleRequests")
@graphql_payload
@require_authentication
async def get_ontology_role_requests(
        _,
        info
) -> List[UserOutput]:
    # Return only users with outstanding role change requests
    context = info.context
    bus = context.get('bus')
    user_id = context.get('user_id')
    async with bus.uow.get_uow(user_id=user_id) as uow_holder:
        ontology_role = uow_holder.ontology.role
        if ontology_role != OntologyRole.ADMIN:
            raise UnauthorisedOperationError("Only ontology admins can see users with ontology role requests")
        requesting_users = [a async for a in uow_holder.views.accounts.get_users_with_ontology_role_requests()]
        return requesting_users

@graphql_query.field("ontologyEditors")
@graphql_payload
@require_authentication
async def get_ontology_editors(
        _,
        info
) -> List[UserOutput]:
    # Return only users with ontology role as editor
    context = info.context
    bus = context.get('bus')
    user_id = context.get('user_id')
    async with bus.uow.get_uow(user_id=user_id) as uow_holder:
        ontology_role = uow_holder.ontology.role
        if ontology_role != OntologyRole.ADMIN:
            raise UnauthorisedOperationError("Only ontology admins can see users with ontology role requests")
        editor_users = [a async for a in uow_holder.views.accounts.get_editors_for_ontology_admin()]
        return editor_users

@graphql_query.field("ontologyAdmins")
@graphql_payload
@require_authentication
async def get_ontology_admins(
        _,
        info
) -> List[UserOutput]:
    # Return only users with ontology role as admin
    context = info.context
    bus = context.get('bus')
    user_id = context.get('user_id')
    async with bus.uow.get_uow(user_id=user_id) as uow_holder:
        ontology_role = uow_holder.ontology.role
        if ontology_role != OntologyRole.ADMIN:
            raise UnauthorisedOperationError("Only ontology admins can see users with ontology role requests")
        admin_users = [a async for a in uow_holder.views.accounts.get_admins_for_ontology_admin()]
        return admin_users