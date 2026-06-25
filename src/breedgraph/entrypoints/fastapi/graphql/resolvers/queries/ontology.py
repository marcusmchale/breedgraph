from ariadne import ObjectType, UnionType, InterfaceType

from src.breedgraph.custom_exceptions import UnauthorisedOperationError
from src.breedgraph.domain.model.ontology import (
    OntologyRelationshipBase,
    OntologyEntryLabel, OntologyRelationshipLabel,
    OntologyCommit,
    Version, LifecyclePhase,
)
from src.breedgraph.service_layer.queries.read_models import Ontology, OntologyEntryOutput

from src.breedgraph.domain.model.accounts import UserOutput, OntologyRole
from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import update_ontology_map, update_users_map

from typing import Dict, List, Tuple

import logging



logger = logging.getLogger(__name__)

from . import graphql_query
from ..registry import graphql_resolvers

# Object types for interfaces and specific types
ontology = ObjectType("Ontology")

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

ontology_relationship = ObjectType("OntologyRelationship")

graphql_resolvers.register_type_resolvers(
    ontology,
    ontology_commit,
    ontology_entry_union, ontology_entry_interface, related_to_terms,
    ontology_relationship,
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

@graphql_query.field("ontologyVersion")
@graphql_payload
@require_authentication
async def get_ontology_version(
    _,
    info
) -> Version:
    bus = info.context.get('bus')
    async with bus.views_factory.get_views() as views:
        version = await views.ontology.get_current_version()
        return version

@graphql_query.field("ontology")
@graphql_payload
@require_authentication
async def get_ontology(
    _,
    info,
    version_id: str|None = None
) -> Ontology:
    bus = info.context.get('bus')
    async with bus.views_factory.get_views() as views:
        if version_id is None:
            version = await views.ontology.get_current_version()
        else:
            try:
                version_id = int(version_id)
            except ValueError:
                raise ValueError("Could not recognize version ID")
            version = Version.from_packed(version_id)
        ontology_version = await views.ontology.get_ontology(version=version)
        await update_ontology_map(
            context=info.context,
            entries=ontology_version.entries
        )
        return ontology_version

#
#@ontology.field('entries')
#async def resolve_ontology_entries(obj, info):
#    return list(obj.entries)
#
#@ontology.field('relationships')
#async def resolve_ontology_entries(obj, info):
#    return obj.relationships
#
@graphql_query.field("ontologyEntries")
@graphql_payload
@require_authentication
async def get_ontology_entries(
        _,
        info,
        entry_ids: List[int] | None = None,
        labels: List[OntologyEntryLabel] | None = None,
        version_id: int|None = None,
        draft: bool = False
) -> List[OntologyEntryOutput]:
    bus = info.context.get('bus')
    async with bus.views_factory.get_views() as views:
        if version_id is None:
            version = await views.ontology.get_current_version()
        else:
            version = Version.from_packed(version_id)
        entries = await views.ontology.get_entries(version=version, entry_ids=entry_ids, labels=labels, draft=draft)
        await update_ontology_map(
            context=info.context,
            entries=entries
        )
        return entries

async def resolve_ontology_entries(context, entry_ids):
    if not entry_ids:
        return []

    ontology_map = context.get('ontology_map')
    entry_ids = set(entry_ids)
    entry_ids.discard(None)
    to_update = entry_ids - ontology_map.keys()
    await update_ontology_map(context, entry_ids=to_update)
    return [ontology_map[entry_id] for entry_id in entry_ids if entry_id in ontology_map]

# Interface resolvers - common to all ontology entries
@ontology_entry_interface.field("versionId")
async def resolve_version_id(obj, _):
    return obj.version.packed_version

# Interface resolvers - common to all ontology entries
@ontology_entry_interface.field("parents")
async def resolve_parents(obj, info):
    return await resolve_ontology_entries(info.context, entry_ids=obj.parents)

@ontology_entry_interface.field("children")
async def resolve_children(obj, info):
    return await resolve_ontology_entries(info.context, entry_ids=obj.children)

@ontology_entry_interface.field("authors")
async def resolve_authors(obj, info):
    return []
    #raise NotImplementedError

@ontology_entry_interface.field("references")
def resolve_references(obj, info):
    return []
    #raise NotImplementedError

@ontology_entry_interface.field("phase")
async def resolve_phase(obj, info):
    return LifecyclePhase(obj.phase)

# Interface resolvers - common to all ontology entries
@ontology_relationship.field("versionId")
async def resolve_version_id(obj, _):
    return obj.version.packed_version

@ontology_relationship.field("phase")
async def resolve_phase(obj, info):
    return LifecyclePhase(obj.phase)

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
    return entries[0] if entries else None

@variable.field("observationMethod")
async def resolve_variable_method(obj, info):
    entries = await resolve_ontology_entries(info.context, entry_ids=[obj.observation_method])
    return entries[0] if entries else None

@variable.field("scale")
async def resolve_variable_scale(obj, info):
    entries = await resolve_ontology_entries(info.context, entry_ids=[obj.scale])
    return entries[0] if entries else None

# ControlMethod-specific resolvers
@control_method.field("factors")
async def resolve_control_method_factors(obj, info):
    return await resolve_ontology_entries(info.context, entry_ids=obj.factors)

# Factor-specific resolvers
@factor.field("condition")
async def resolve_factor_condition(obj, info):
    entries = await resolve_ontology_entries(info.context, entry_ids=[obj.condition])
    return entries[0] if entries else None

@factor.field("controlMethod")
async def resolve_factor_control_method(obj, info):
    entries = await resolve_ontology_entries(info.context, entry_ids=[obj.control_method])
    return entries[0] if entries else None

@factor.field("scale")
async def resolve_factor_scale(obj, info):
    entries = await resolve_ontology_entries(info.context, entry_ids=[obj.scale])
    return entries[0] if entries else None

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
    # todo consider making the commit history a view rather than relying on the full service
    async with bus.uow_factory.get_uow(user_id=user_id) as uow:
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
    async with bus.views_factory.get_views(user_id=user_id) as views:
        requesting_users = [a async for a in views.accounts.get_users_with_ontology_role_requests()]
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
    async with bus.views_factory.get_views(user_id=user_id) as views:
        editor_users = [a async for a in views.accounts.get_editors_for_ontology_admin()]
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
    async with bus.views_factory.get_views(user_id=user_id) as views:
        ontology_role = views.ontology.role
        if ontology_role != OntologyRole.ADMIN:
            raise UnauthorisedOperationError("Only ontology admins can see users with ontology role requests")
        admin_users = [a async for a in views.accounts.get_admins_for_ontology_admin()]
        return admin_users