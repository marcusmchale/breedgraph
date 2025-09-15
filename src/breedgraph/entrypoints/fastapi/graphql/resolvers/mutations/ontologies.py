from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from src.breedgraph.domain.commands.ontologies import (
    CommitOntology,
    CreateTerm, CreateSubject, CreateTrait, CreateCondition,
    CreateScale, CreateScaleCategory, CreateObservationMethod, CreateVariable,
    CreateControlMethod, CreateFactor, CreateEventType, CreateGermplasmMethod,
    CreateLocationType, CreateDesign, CreateLayoutType
)
from src.breedgraph.domain.model.ontology import VersionChange


import logging
logger = logging.getLogger(__name__)

from . import graphql_mutation

@graphql_mutation.field("ontology_commit_version")
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
        user=user_id,
        version_change=version_change.value(),
        comment=comment,
        licence=licence_reference,
        copyright=copyright_reference

    )
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontology_create_term")
@graphql_payload
@require_authentication
async def create_term(_, info, entry: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates term: {entry}")
    cmd = CreateTerm(user=user_id, **entry)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontology_create_subject")
@graphql_payload
@require_authentication
async def create_subject(_, info, entry: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates subject: {entry}")
    cmd = CreateSubject(user=user_id, **entry)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontology_create_trait")
@graphql_payload
@require_authentication
async def create_trait(_, info, entry: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates trait: {entry}")
    cmd = CreateTrait(user=user_id, **entry)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontology_create_condition")
@graphql_payload
@require_authentication
async def create_condition(_, info, entry: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates condition: {entry}")
    cmd = CreateCondition(user=user_id, **entry)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontology_create_scale")
@graphql_payload
@require_authentication
async def create_scale(_, info, entry: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates scale: {entry}")
    cmd = CreateScale(user=user_id, **entry)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontology_create_scale_category")
@graphql_payload
@require_authentication
async def create_scale_category(_, info, entry: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates scale category: {entry}")
    cmd = CreateScaleCategory(user=user_id, **entry)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontology_create_observation_method")
@graphql_payload
@require_authentication
async def create_observation_method(_, info, entry: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates observation method: {entry}")
    cmd = CreateObservationMethod(user=user_id, **entry)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontology_create_variable")
@graphql_payload
@require_authentication
async def create_variable(_, info, entry: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates variable: {entry}")
    cmd = CreateVariable(user=user_id, **entry)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontology_create_control_method")
@graphql_payload
@require_authentication
async def create_control_method(_, info, entry: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates control method: {entry}")
    cmd = CreateControlMethod(user=user_id, **entry)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontology_create_parameter")
@graphql_payload
@require_authentication
async def create_parameter(_, info, entry: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates parameter: {entry}")
    cmd = CreateFactor(user=user_id, **entry)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontology_create_event")
@graphql_payload
@require_authentication
async def create_event(_, info, entry: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates event: {entry}")
    cmd = CreateEventType(user=user_id, **entry)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontology_create_germplasm_method")
@graphql_payload
@require_authentication
async def create_germplasm_method(_, info, entry: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates germplasm method: {entry}")
    cmd = CreateGermplasmMethod(user=user_id, **entry)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontology_create_location_type")
@graphql_payload
@require_authentication
async def create_location_type(_, info, entry: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates location type: {entry}")
    cmd = CreateLocationType(user=user_id, **entry)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontology_create_design")
@graphql_payload
@require_authentication
async def create_design(_, info, entry: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates design: {entry}")
    cmd = CreateDesign(user=user_id, **entry)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("ontology_create_layout_type")
@graphql_payload
@require_authentication
async def create_layout_type(_, info, entry: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates layout type: {entry}")
    cmd = CreateLayoutType(user=user_id, **entry)
    await info.context['bus'].handle(cmd)
    return True