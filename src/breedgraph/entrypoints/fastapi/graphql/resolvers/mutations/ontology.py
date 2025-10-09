from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from src.breedgraph.domain.commands.ontologies import (
    CommitOntologyVersion,
    ActivateOntologyEntries, DeprecateOntologyEntries, RemoveOntologyEntries,
    ActivateOntologyRelationships, DeprecateOntologyRelationships, RemoveOntologyRelationships,
    CreateTerm, CreateSubject, CreateTrait, CreateCondition,
    CreateScale, CreateScaleCategory, CreateObservationMethod, CreateVariable,
    CreateControlMethod, CreateFactor, CreateEventType,
    CreateLocationType, CreateDesign, CreateLayoutType,
    UpdateTerm, UpdateSubject, UpdateTrait, UpdateCondition,
    UpdateScale, UpdateCategory, UpdateObservationMethod, UpdateVariable,
    UpdateControlMethod, UpdateFactor, UpdateEventType,
    UpdateLocationType, UpdateDesign, UpdateLayoutType

)
from src.breedgraph.domain.model.ontology import VersionChange
from typing import List

import logging
logger = logging.getLogger(__name__)

from . import graphql_mutation

@graphql_mutation.field("ontologyCommitVersion")
@graphql_payload
@require_authentication
async def commit_version(
        _,
        info,
        version_change: VersionChange = VersionChange.PATCH,
        comment: str = '',
        licence_id: int = None,
        copyright_id: int = None
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} commits {version_change} change to ontology ")
    cmd = CommitOntologyVersion(
        agent_id=user_id,
        version_change=version_change,
        comment=comment,
        licence=licence_id,
        copyright=copyright_id
    )
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyActivateEntries")
@graphql_payload
@require_authentication
async def activate_entries(
        _,
        info,
        entry_ids: List[int]
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} marks entries {entry_ids} as active")
    cmd = ActivateOntologyEntries(
        agent_id=user_id,
        entry_ids=entry_ids
    )
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyDeprecateEntries")
@graphql_payload
@require_authentication
async def deprecate_entries(
        _,
        info,
        entry_ids: List[int]
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} marks entries {entry_ids} as deprecated")
    cmd = DeprecateOntologyEntries(
        agent_id=user_id,
        entry_ids=entry_ids
    )
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyRemoveEntries")
@graphql_payload
@require_authentication
async def remove_entries(
        _,
        info,
        entry_ids: List[int]
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} marks entries {entry_ids} as removed")
    cmd = RemoveOntologyEntries(
        agent_id=user_id,
        entry_ids=entry_ids
    )
    await info.context['bus'].handle(cmd)
    return True


@graphql_mutation.field("ontologyActivateRelationships")
@graphql_payload
@require_authentication
async def activate_relationships(
        _,
        info,
        relationship_ids: List[int]
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} marks relationships {relationship_ids} as active")
    cmd = ActivateOntologyRelationships(
        agent_id=user_id,
        relationship_ids=relationship_ids
    )
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyDeprecateRelationships")
@graphql_payload
@require_authentication
async def deprecate_relationships(
        _,
        info,
        relationship_ids: List[int]
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} marks relationships {relationship_ids} as deprecated")
    cmd = DeprecateOntologyRelationships(
        agent_id=user_id,
        relationship_ids=relationship_ids
    )
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyRemoveRelationships")
@graphql_payload
@require_authentication
async def remove_relationships(
        _,
        info,
        relationship_ids: List[int]
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} marks relationships {relationship_ids} as removed")
    cmd = RemoveOntologyRelationships(
        agent_id=user_id,
        relationship_ids=relationship_ids
    )
    await info.context['bus'].handle(cmd)
    return True


@graphql_mutation.field("ontologyCreateTerm")
@graphql_payload
@require_authentication
async def create_term(_, info, term: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates term: {term}")
    cmd = CreateTerm(agent_id=user_id, **term)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyCreateSubject")
@graphql_payload
@require_authentication
async def create_subject(_, info, subject: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates subject: {subject}")
    cmd = CreateSubject(agent_id=user_id, **subject)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyCreateTrait")
@graphql_payload
@require_authentication
async def create_trait(_, info, trait: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates trait: {trait}")
    cmd = CreateTrait(agent_id=user_id, **trait)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyCreateCondition")
@graphql_payload
@require_authentication
async def create_condition(_, info, condition: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates condition: {condition}")
    cmd = CreateCondition(agent_id=user_id, **condition)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyCreateScale")
@graphql_payload
@require_authentication
async def create_scale(_, info, scale: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates scale: {scale}")
    cmd = CreateScale(agent_id=user_id, **scale)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyCreateCategory")
@graphql_payload
@require_authentication
async def create_category(_, info, category: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates scale category: {category}")
    cmd = CreateScaleCategory(agent_id=user_id, **category)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyCreateObservationMethod")
@graphql_payload
@require_authentication
async def create_observation_method(_, info, observation_method: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates observation method: {observation_method}")
    cmd = CreateObservationMethod(agent_id=user_id, **observation_method)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyCreateVariable")
@graphql_payload
@require_authentication
async def create_variable(_, info, variable: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates variable: {variable}")
    cmd = CreateVariable(agent_id=user_id, **variable)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyCreateControlMethod")
@graphql_payload
@require_authentication
async def create_control_method(_, info, control_method: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates control method: {control_method}")
    cmd = CreateControlMethod(agent_id=user_id, **control_method)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyCreateFactor")
@graphql_payload
@require_authentication
async def create_factor(_, info, factor: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates factor: {factor}")
    cmd = CreateFactor(agent_id=user_id, **factor)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyCreateEvent")
@graphql_payload
@require_authentication
async def create_event(_, info, event: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates event: {event}")
    cmd = CreateEventType(agent_id=user_id, **event)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyCreateLocationType")
@graphql_payload
@require_authentication
async def create_location_type(_, info, location_type: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates location type: {location_type}")
    cmd = CreateLocationType(agent_id=user_id, **location_type)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyCreateDesign")
@graphql_payload
@require_authentication
async def create_design(_, info, design: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates design: {design}")
    cmd = CreateDesign(agent_id=user_id, **design)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyCreateLayoutType")
@graphql_payload
@require_authentication
async def create_layout_type(_, info, layout_type: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates layout type: {layout_type}")
    cmd = CreateLayoutType(agent_id=user_id, **layout_type)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyUpdateTerm")
@graphql_payload
@require_authentication
async def update_term(_, info, term: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} updates term: {term}")
    cmd = UpdateTerm(agent_id=user_id, **term)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyUpdateSubject")
@graphql_payload
@require_authentication
async def update_subject(_, info, subject: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} updates subject: {subject}")
    cmd = UpdateSubject(agent_id=user_id, **subject)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyUpdateTrait")
@graphql_payload
@require_authentication
async def update_trait(_, info, trait: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} updates trait: {trait}")
    cmd = UpdateTrait(agent_id=user_id, **trait)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyUpdateCondition")
@graphql_payload
@require_authentication
async def update_condition(_, info, condition: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} updates condition: {condition}")
    cmd = UpdateCondition(agent_id=user_id, **condition)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyUpdateScale")
@graphql_payload
@require_authentication
async def update_scale(_, info, scale: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} updates scale: {scale}")
    cmd = UpdateScale(agent_id=user_id, **scale)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyUpdateCategory")
@graphql_payload
@require_authentication
async def update_category(_, info, category: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} updates scale category: {category}")
    cmd = UpdateCategory(agent_id=user_id, **category)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyUpdateObservationMethod")
@graphql_payload
@require_authentication
async def update_observation_method(_, info, observation_method: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} updates observation method: {observation_method}")
    cmd = UpdateObservationMethod(agent_id=user_id, **observation_method)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyUpdateVariable")
@graphql_payload
@require_authentication
async def update_variable(_, info, variable: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} updates variable: {variable}")
    cmd = UpdateVariable(agent_id=user_id, **variable)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyUpdateControlMethod")
@graphql_payload
@require_authentication
async def update_control_method(_, info, control_method: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} updates control method: {control_method}")
    cmd = UpdateControlMethod(agent_id=user_id, **control_method)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyUpdateFactor")
@graphql_payload
@require_authentication
async def update_factor(_, info, factor: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} updates factor: {factor}")
    cmd = UpdateFactor(agent_id=user_id, **factor)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyUpdateEvent")
@graphql_payload
@require_authentication
async def update_event(_, info, event: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} updates event: {event}")
    cmd = UpdateEventType(agent_id=user_id, **event)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyUpdateLocationType")
@graphql_payload
@require_authentication
async def update_location_type(_, info, location_type: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} updates location type: {location_type}")
    cmd = UpdateLocationType(agent_id=user_id, **location_type)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyUpdateDesign")
@graphql_payload
@require_authentication
async def update_design(_, info, design: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} updates design: {design}")
    cmd = UpdateDesign(agent_id=user_id, **design)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyUpdateLayoutType")
@graphql_payload
@require_authentication
async def update_layout_type(_, info, layout_type: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} updates layout type: {layout_type}")
    cmd = UpdateLayoutType(agent_id=user_id, **layout_type)
    await info.context['bus'].handle(cmd)
    return True