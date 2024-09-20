from src.breedgraph.domain.model.ontology import ObservationMethodType, ScaleType
from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload
from src.breedgraph.domain.commands.ontologies import (
    AddTerm,
    AddSubject,
    AddRole,
    AddEvent,
    AddTitle,
    AddScale,
    AddTrait,
    AddCategory,
    AddExposure,
    AddVariable,
    AddCondition,
    AddParameter,
    AddDesignType,
    AddLayoutType,
    AddLocationType,
    AddGermplasmMethod,
    AddObservationMethod

)
from src.breedgraph.custom_exceptions import UnauthorisedOperationError
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.mutations import graphql_mutation

from typing import List


import logging
logger = logging.getLogger(__name__)

@graphql_mutation.field("add_term")
@graphql_payload
async def add_term(
        _,
        info,
        entry: dict
) -> bool:
    user_id = info.context.get('user_id')
    if user_id is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    logger.debug(f"User {user_id} adds term: {entry}")
    cmd = AddTerm(user=user_id, **entry)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("add_subject")
@graphql_payload
async def add_subject(
        _,
        info,
        entry: dict
) -> bool:
    user_id = info.context.get('user_id')
    if user_id is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    logger.debug(f"User {user_id} adds subject: {entry}")
    cmd = AddSubject(user=user_id, **entry)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("add_location_type")
@graphql_payload
async def add_location_type(
        _,
        info,
        entry: dict
) -> bool:
    user_id = info.context.get('user_id')
    if user_id is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    logger.debug(f"User {user_id} adds location type: {entry}")
    cmd = AddLocationType(user=user_id, **entry)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("add_layout_type")
@graphql_payload
async def add_layout_type(
        _,
        info,
        entry: dict
) -> bool:
    user_id = info.context.get('user_id')
    if user_id is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    logger.debug(f"User {user_id} adds layout type: {entry}")
    cmd = AddLayoutType(user=user_id, **entry)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("add_design_type")
@graphql_payload
async def add_design_type(
        _,
        info,
        entry: dict
) -> bool:
    user_id = info.context.get('user_id')
    if user_id is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    logger.debug(f"User {user_id} adds design: {entry}")
    cmd = AddDesignType(user=user_id, **entry)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("add_role")
@graphql_payload
async def add_role(
        _,
        info,
        entry: dict
) -> bool:
    user_id = info.context.get('user_id')
    if user_id is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    logger.debug(f"User {user_id} adds role: {entry}")
    cmd = AddRole(user=user_id, **entry)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("add_title")
@graphql_payload
async def add_title(
        _,
        info,
        entry: dict
) -> bool:
    user_id = info.context.get('user_id')
    if user_id is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    logger.debug(f"User {user_id} adds title: {entry}")
    cmd = AddTitle(user=user_id, **entry)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("add_germplasm_method")
@graphql_payload
async def add_germplasm_method(
        _,
        info,
        entry: dict
) -> bool:
    user_id = info.context.get('user_id')
    if user_id is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    logger.debug(f"User {user_id} adds germplasm method: {entry}")
    cmd = AddGermplasmMethod(user=user_id, **entry)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("add_observation_method")
@graphql_payload
async def add_observation_method(
        _,
        info,
        entry: dict,
        method_type: ObservationMethodType
) -> bool:
    user_id = info.context.get('user_id')
    if user_id is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    logger.debug(f"User {user_id} adds observation method: {entry}")
    cmd = AddObservationMethod(user=user_id, method_type=method_type, **entry)
    await info.context['bus'].handle(cmd)
    return True


@graphql_mutation.field("add_scale")
@graphql_payload
async def add_scale(
        _,
        info,
        entry: dict,
        scale_type: ScaleType
) -> bool:
    user_id = info.context.get('user_id')
    if user_id is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    logger.debug(f"User {user_id} adds scale: {entry}")
    cmd = AddScale(user=user_id, scale_type=scale_type, **entry)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("add_category")
@graphql_payload
async def add_category(
        _,
        info,
        entry: dict,
        scale: int,
        rank: int = None
) -> bool:
    user_id = info.context.get('user_id')
    if user_id is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    logger.debug(f"User {user_id} adds scale: {entry}")
    cmd = AddCategory(user=user_id, scale=scale, rank=rank, **entry)
    await info.context['bus'].handle(cmd)
    return True


@graphql_mutation.field("add_trait")
@graphql_payload
async def add_trait(
        _,
        info,
        entry: dict,
        subjects: List[int] = None
) -> bool:
    user_id = info.context.get('user_id')
    if user_id is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    logger.debug(f"User {user_id} adds trait: {entry}")
    cmd = AddTrait(user=user_id, subjects=subjects, **entry)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("add_variable")
@graphql_payload
async def add_variable(
        _,
        info,
        entry: dict,
        trait: int,
        method: int,
        scale: int
) -> bool:
    user_id = info.context.get('user_id')
    if user_id is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    logger.debug(f"User {user_id} adds variable: {entry}")
    cmd = AddVariable(user=user_id, trait=trait, method=method, scale=scale, **entry)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("add_condition")
@graphql_payload
async def add_condition(
        _,
        info,
        entry: dict
) -> bool:
    user_id = info.context.get('user_id')
    if user_id is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    logger.debug(f"User {user_id} adds condition: {entry}")
    cmd = AddCondition(user=user_id, **entry)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("add_parameter")
@graphql_payload
async def add_parameter(
        _,
        info,
        entry: dict,
        condition: int,
        method: int,
        scale: int
) -> bool:
    user_id = info.context.get('user_id')
    if user_id is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    logger.debug(f"User {user_id} adds variable: {entry}")
    cmd = AddParameter(user=user_id, condition=condition, method=method, scale=scale, **entry)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("add_exposure")
@graphql_payload
async def add_exposure(
        _,
        info,
        entry: dict
) -> bool:
    user_id = info.context.get('user_id')
    if user_id is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    logger.debug(f"User {user_id} adds exposure: {entry}")
    cmd = AddExposure(user=user_id, **entry)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("add_event")
@graphql_payload
async def add_event(
        _,
        info,
        entry: dict,
        exposure: int,
        method: int,
        scale: int
) -> bool:
    user_id = info.context.get('user_id')
    if user_id is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    logger.debug(f"User {user_id} adds variable: {entry}")
    cmd = AddEvent(user=user_id, exposure=exposure, method=method, scale=scale, **entry)
    await info.context['bus'].handle(cmd)
    return True
