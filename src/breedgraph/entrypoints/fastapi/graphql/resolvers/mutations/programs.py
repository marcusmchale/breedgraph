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
@graphql_mutation.field("programsCreateProgram")
@graphql_payload
@require_authentication
async def create_program(
        _,
        info,
        program: dict
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"Create program: {program} by user {user_id}")

    cmd = CreateProgram(agent_id=user_id, **program)
    await info.context['bus'].handle(cmd)
    return True


@graphql_mutation.field("programsUpdateProgram")
@graphql_payload
@require_authentication
async def update_program(
        _,
        info,
        program: dict
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"Update program: {program} by user {user_id}")

    cmd = UpdateProgram(agent_id=user_id, **program)
    await info.context['bus'].handle(cmd)
    return True


@graphql_mutation.field("programsDeleteProgram")
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
        agent_id=user_id,
        program_id=program_id
    )
    await info.context['bus'].handle(cmd)
    return True


# Trial mutations
@graphql_mutation.field("programsCreateTrial")
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
        reference_ids: List[int] = None
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"Create trial: {name} in program {program_id} by user {user_id}")

    cmd = CreateTrial(
        agent_id=user_id,
        program_id=program_id,
        name=name,
        fullname=fullname,
        description=description,
        start=start,
        end=end,
        contacts=contact_ids,
        references=reference_ids
    )
    await info.context['bus'].handle(cmd)
    return True


@graphql_mutation.field("programsUpdateTrial")
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
        reference_ids: List[int] = None
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"Update trial: {trial_id} by user {user_id}")

    cmd = UpdateTrial(
        agent_id=user_id,
        trial_id=trial_id,
        name=name,
        fullname=fullname,
        description=description,
        start=start,
        end=end,
        contacts=contact_ids,
        references=reference_ids
    )
    await info.context['bus'].handle(cmd)
    return True


@graphql_mutation.field("programsDeleteTrial")
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
        agent_id=user_id,
        trial_id=trial_id
    )
    await info.context['bus'].handle(cmd)
    return True


# Study mutations
@graphql_mutation.field("programsCreateStudy")
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
        dataset_ids: List[int] = None,
        design_id: int = None,
        licence_id: int = None,
        reference_ids: List[int] = None
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"Create study: {name} in trial {trial_id} by user {user_id}")

    cmd = CreateStudy(
        agent_id=user_id,
        trial_id=trial_id,
        name=name,
        fullname=fullname,
        description=description,
        practices=practices,
        start=start,
        end=end,
        datasets=dataset_ids,
        design=design_id,
        licence=licence_id,
        references=reference_ids
    )
    await info.context['bus'].handle(cmd)
    return True


@graphql_mutation.field("programsUpdateStudy")
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
        dataset_ids: List[int] = None,
        design_id: int = None,
        licence_id: int = None,
        reference_ids: List[int] = None
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"Update study: {study_id} by user {user_id}")

    cmd = UpdateStudy(
        agent_id=user_id,
        study_id=study_id,
        name=name,
        fullname=fullname,
        description=description,
        practices=practices,
        start=start,
        end=end,
        datasets=dataset_ids,
        design=design_id,
        licence=licence_id,
        references=reference_ids
    )
    await info.context['bus'].handle(cmd)
    return True


@graphql_mutation.field("programsDeleteStudy")
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
        agent_id=user_id,
        study_id=study_id
    )
    await info.context['bus'].handle(cmd)
    return True