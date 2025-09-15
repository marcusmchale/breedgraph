from src.breedgraph.domain.model.programs import ProgramInput
from src.breedgraph.domain.commands.programs import (
    CreateProgram, UpdateProgram, DeleteProgram,
    CreateTrial, UpdateTrial, DeleteTrial,
    CreateStudy, UpdateStudy, DeleteStudy
)
from src.breedgraph.domain.model.controls import ReadRelease
from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from typing import List

import logging
logger = logging.getLogger(__name__)

from . import graphql_mutation

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
        program_id: int
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"Delete program: {program_id} by user {user_id}")

    cmd = DeleteProgram(
        user=user_id,
        program=program_id
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
        program_id: int,
        name: str,
        fullname: str = None,
        description: str = None,
        start: str = None,  # Will be converted to PyDT64
        end: str = None,  # Will be converted to PyDT64
        contact_ids: List[int] = None,
        reference_ids: List[int] = None,
        release: str = ReadRelease.REGISTERED.name
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"Create trial: {name} in program {program_id} by user {user_id}")

    cmd = CreateTrial(
        user=user_id,
        program=program_id,
        name=name,
        fullname=fullname,
        description=description,
        start=start,
        end=end,
        contacts=contact_ids,
        references=reference_ids,
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
        trial_id: int,
        name: str = None,
        fullname: str = None,
        description: str = None,
        start: str = None,
        end: str = None,
        contact_ids: List[int] = None,
        reference_ids: List[int] = None,
        release: str = None
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"Update trial: {trial_id} by user {user_id}")

    cmd = UpdateTrial(
        user=user_id,
        trial=trial_id,
        name=name,
        fullname=fullname,
        description=description,
        start=start,
        end=end,
        contacts=contact_ids,
        references=reference_ids,
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
        trial_id: int
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"Delete trial: {trial_id} by user {user_id}")

    cmd = DeleteTrial(
        user=user_id,
        trial=trial_id
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
        trial_id: int,
        name: str,
        fullname: str = None,
        description: str = None,
        practices: str = None,
        start: str = None,
        end: str = None,
        factor_ids: List[int] = None,
        observation_ids: List[int] = None,
        design_id: int = None,
        licence_id: int = None,
        reference_ids: List[int] = None,
        release: str = ReadRelease.REGISTERED.name
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"Create study: {name} in trial {trial_id} by user {user_id}")

    cmd = CreateStudy(
        user=user_id,
        trial=trial_id,
        name=name,
        fullname=fullname,
        description=description,
        practices=practices,
        start=start,
        end=end,
        factors=factor_ids,
        observations=observation_ids,
        design=design_id,
        licence=licence_id,
        references=reference_ids,
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
        study_id: int,
        name: str = None,
        fullname: str = None,
        description: str = None,
        practices: str = None,
        start: str = None,
        end: str = None,
        factor_ids: List[int] = None,
        observation_ids: List[int] = None,
        design_id: int = None,
        licence_id: int = None,
        reference_ids: List[int] = None,
        release: str = None
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"Update study: {study_id} by user {user_id}")

    cmd = UpdateStudy(
        user=user_id,
        study=study_id,
        name=name,
        fullname=fullname,
        description=description,
        practices=practices,
        start=start,
        end=end,
        factors=factor_ids,
        observations=observation_ids,
        design=design_id,
        licence=licence_id,
        references=reference_ids,
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
        study_id: int
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"Delete study: {study_id} by user {user_id}")

    cmd = DeleteStudy(
        user=user_id,
        study=study_id
    )
    await info.context['bus'].handle(cmd)
    return True