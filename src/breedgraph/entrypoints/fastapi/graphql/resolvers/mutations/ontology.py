from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from src.breedgraph.domain.commands.ontologies import (
    CommitOntology,
    CreateTerm, CreateSubject, CreateTrait, CreateCondition,
    CreateScale, CreateScaleCategory, CreateObservationMethod, CreateVariable,
    CreateControlMethod, CreateFactor, CreateEventType,
    CreateLocationType, CreateDesign, CreateLayoutType
)
from src.breedgraph.domain.model.ontology import VersionChange


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
        licence_reference: int = None,
        copyright_reference: int = None
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} commits {version_change} change to ontology ")
    cmd = CommitOntology(
        agent_id=user_id,
        version_change=version_change.value(),
        comment=comment,
        licence=licence_reference,
        copyright=copyright_reference

    )
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyCreateTerm")
@graphql_payload
@require_authentication
async def create_term(_, info, term_input: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates term: {term_input}")
    cmd = CreateTerm(agent_id=user_id, **term_input)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyCreateSubject")
@graphql_payload
@require_authentication
async def create_subject(_, info, subject_input: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates subject: {subject_input}")
    cmd = CreateSubject(agent_id=user_id, **subject_input)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyCreateTrait")
@graphql_payload
@require_authentication
async def create_trait(_, info, trait_input: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates trait: {trait_input}")
    cmd = CreateTrait(agent_id=user_id, **trait_input)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyCreateCondition")
@graphql_payload
@require_authentication
async def create_condition(_, info, condition_input: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates condition: {condition_input}")
    cmd = CreateCondition(agent_id=user_id, **condition_input)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyCreateScale")
@graphql_payload
@require_authentication
async def create_scale(_, info, scale_input: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates scale: {scale_input}")
    cmd = CreateScale(agent_id=user_id, **scale_input)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyCreateScaleCategory")
@graphql_payload
@require_authentication
async def create_scale_category(_, info, scale_category_input: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates scale category: {scale_category_input}")
    cmd = CreateScaleCategory(agent_id=user_id, **scale_category_input)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyCreateObservationMethod")
@graphql_payload
@require_authentication
async def create_observation_method(_, info, observation_method_input: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates observation method: {observation_method_input}")
    cmd = CreateObservationMethod(agent_id=user_id, **observation_method_input)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyCreateVariable")
@graphql_payload
@require_authentication
async def create_variable(_, info, variable_input: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates variable: {variable_input}")
    cmd = CreateVariable(agent_id=user_id, **variable_input)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyCreateControlMethod")
@graphql_payload
@require_authentication
async def create_control_method(_, info, control_method_input: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates control method: {control_method_input}")
    cmd = CreateControlMethod(agent_id=user_id, **control_method_input)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyCreateFactor")
@graphql_payload
@require_authentication
async def create_factor(_, info, factor_input: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates factor: {factor_input}")
    cmd = CreateFactor(agent_id=user_id, **factor_input)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyCreateEvent")
@graphql_payload
@require_authentication
async def create_event(_, info, event_input: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates event: {event_input}")
    cmd = CreateEventType(agent_id=user_id, **event_input)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyCreateLocationType")
@graphql_payload
@require_authentication
async def create_location_type(_, info, location_type_input: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates location type: {location_type_input}")
    cmd = CreateLocationType(agent_id=user_id, **location_type_input)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyCreateDesign")
@graphql_payload
@require_authentication
async def create_design(_, info, design_input: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates design: {design_input}")
    cmd = CreateDesign(agent_id=user_id, **design_input)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontologyCreateLayoutType")
@graphql_payload
@require_authentication
async def create_layout_type(_, info, layout_type_input: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates layout type: {layout_type_input}")
    cmd = CreateLayoutType(agent_id=user_id, **layout_type_input)
    await info.context['bus'].handle(cmd)
    return True