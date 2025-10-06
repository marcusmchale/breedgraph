from src.breedgraph.domain.model.programs import ProgramInput, TrialInput, StudyInput
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
        trial: dict
) -> bool:
    user_id = info.context.get('user_id')

    logger.debug(f"Create trial: {trial.get('name')} in program {trial.get('program_id')} by user {user_id}")
    cmd = CreateTrial(
        agent_id=user_id,
        **trial
    )
    await info.context['bus'].handle(cmd)
    return True


@graphql_mutation.field("programsUpdateTrial")
@graphql_payload
@require_authentication
async def update_trial(
        _,
        info,
        trial: dict
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"Update trial: {trial.get('id')} by user {user_id}")
    cmd = UpdateTrial(
        agent_id=user_id,
        trial_id=trial.get('trial_id'),
        name=trial.get('name'),
        fullname=trial.get('fullname'),
        description=trial.get('description'),
        start=trial.get('start'),
        end=trial.get('end'),
        contact_ids=trial.get('contact_ids'),
        reference_ids=trial.get('reference_ids')
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
        study: dict
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"Create study: {study.get('name')} in trial {study.get('trial_id')} by user {user_id}")

    cmd = CreateStudy(
        agent_id=user_id,
        trial_id=study.get('trial_id'),
        name=study.get('name'),
        fullname=study.get('fullname'),
        description=study.get('description'),
        practices=study.get('practices'),
        start=study.get('start'),
        end=study.get('end'),
        dataset_ids=study.get('dataset_ids'),
        design_id=study.get('design_id'),
        licence_id=study.get('licence_id'),
        reference_ids=study.get('reference_ids')
    )
    await info.context['bus'].handle(cmd)
    return True


@graphql_mutation.field("programsUpdateStudy")
@graphql_payload
@require_authentication
async def update_study(
        _,
        info,
        study
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"Update study: {study.get('id')} by user {user_id}")

    cmd = UpdateStudy(
        agent_id=user_id,
        study_id=study.get('study_id'),
        name=study.get('name'),
        fullname=study.get('fullname'),
        description=study.get('description'),
        practices=study.get('practices'),
        start=study.get('start'),
        end=study.get('end'),
        dataset_ids=study.get('dataset_ids'),
        design_id=study.get('design_id'),
        licence_id=study.get('licence_id'),
        reference_ids=study.get('reference_ids'),
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