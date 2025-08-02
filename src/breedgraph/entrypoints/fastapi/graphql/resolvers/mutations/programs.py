from src.breedgraph.domain.model.programs import ProgramInput
from src.breedgraph.domain.commands.programs import (
    CreateProgram, UpdateProgram, DeleteProgram,
    CreateTrial, UpdateTrial, DeleteTrial,
    CreateStudy, UpdateStudy, DeleteStudy
)
from src.breedgraph.domain.model.controls import ReadRelease
from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.mutations import graphql_mutation
from typing import List

import logging
logger = logging.getLogger(__name__)


# Program mutations
@graphql_mutation.field("create_program")
@graphql_payload
@require_authentication
async def create_program(
        _,
        info,
        program: dict
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"Create program: {program} by user {user_id}")

    cmd = CreateProgram(user=user_id, **program)
    await info.context['bus'].handle(cmd)
    return True


@graphql_mutation.field("update_program")
@graphql_payload
@require_authentication
async def update_program(
        _,
        info,
        program: dict
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"Update program: {program} by user {user_id}")

    cmd = UpdateProgram(user=user_id, **program)
    await info.context['bus'].handle(cmd)
    return True


@graphql_mutation.field("delete_program")
@graphql_payload
@require_authentication
async def delete_program(
        _,
        info,
        program: int
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"Delete program: {program} by user {user_id}")

    cmd = DeleteProgram(
        user=user_id,
        program=program
    )
    await info.context['bus'].handle(cmd)
    return True


# Trial mutations
@graphql_mutation.field("create_trial")
@graphql_payload
@require_authentication
async def create_trial(
        _,
        info,
        program: int,
        name: str,
        fullname: str = None,
        description: str = None,
        start: str = None,  # Will be converted to PyDT64
        end: str = None,  # Will be converted to PyDT64
        contacts: List[int] = None,
        references: List[int] = None,
        release: str = ReadRelease.REGISTERED.name
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"Create trial: {name} in program {program} by user {user_id}")

    cmd = CreateTrial(
        user=user_id,
        program=program,
        name=name,
        fullname=fullname,
        description=description,
        start=start,
        end=end,
        contacts=contacts or [],
        references=references or [],
        release=release
    )
    await info.context['bus'].handle(cmd)
    return True


@graphql_mutation.field("update_trial")
@graphql_payload
@require_authentication
async def update_trial(
        _,
        info,
        trial: int,
        name: str = None,
        fullname: str = None,
        description: str = None,
        start: str = None,
        end: str = None,
        contacts: List[int] = None,
        references: List[int] = None,
        release: str = None
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"Update trial: {trial} by user {user_id}")

    cmd = UpdateTrial(
        user=user_id,
        trial=trial,
        name=name,
        fullname=fullname,
        description=description,
        start=start,
        end=end,
        contacts=contacts,
        references=references,
        release=release
    )
    await info.context['bus'].handle(cmd)
    return True


@graphql_mutation.field("delete_trial")
@graphql_payload
@require_authentication
async def delete_trial(
        _,
        info,
        trial: int
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"Delete trial: {trial} by user {user_id}")

    cmd = DeleteTrial(
        user=user_id,
        trial=trial
    )
    await info.context['bus'].handle(cmd)
    return True


# Study mutations
@graphql_mutation.field("create_study")
@graphql_payload
@require_authentication
async def create_study(
        _,
        info,
        trial: int,
        name: str,
        fullname: str = None,
        description: str = None,
        external_id: str = None,
        practices: str = None,
        start: str = None,
        end: str = None,
        factors: List[int] = None,
        observations: List[int] = None,
        design: int = None,
        licence: int = None,
        references: List[int] = None,
        release: str = ReadRelease.REGISTERED.name
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"Create study: {name} in trial {trial} by user {user_id}")

    cmd = CreateStudy(
        user=user_id,
        trial=trial,
        name=name,
        fullname=fullname,
        description=description,
        external_id=external_id,
        practices=practices,
        start=start,
        end=end,
        factors=factors or [],
        observations=observations or [],
        design=design,
        licence=licence,
        references=references or [],
        release=release
    )
    await info.context['bus'].handle(cmd)
    return True


@graphql_mutation.field("update_study")
@graphql_payload
@require_authentication
async def update_study(
        _,
        info,
        study: int,
        name: str = None,
        fullname: str = None,
        description: str = None,
        external_id: str = None,
        practices: str = None,
        start: str = None,
        end: str = None,
        factors: List[int] = None,
        observations: List[int] = None,
        design: int = None,
        licence: int = None,
        references: List[int] = None,
        release: str = None
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"Update study: {study} by user {user_id}")

    cmd = UpdateStudy(
        user=user_id,
        study=study,
        name=name,
        fullname=fullname,
        description=description,
        external_id=external_id,
        practices=practices,
        start=start,
        end=end,
        factors=factors,
        observations=observations,
        design=design,
        licence=licence,
        references=references,
        release=release
    )
    await info.context['bus'].handle(cmd)
    return True


@graphql_mutation.field("delete_study")
@graphql_payload
@require_authentication
async def delete_study(
        _,
        info,
        study: int
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"Delete study: {study} by user {user_id}")

    cmd = DeleteStudy(
        user=user_id,
        study=study
    )
    await info.context['bus'].handle(cmd)
    return True