from typing import List

from breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from breedgraph.domain.commands.datasets import (
    SubmitRecords,
    UpdateRecords,
    RemoveRecords
)

import logging
logger = logging.getLogger(__name__)

from . import graphql_mutation


@graphql_mutation.field("datasetsSubmitRecords")
@graphql_payload
@require_authentication
async def submit_records(
        _,
        info,
        dataset: dict
) -> str:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} adds dataset for concept: {dataset.get("concept_id")}")
    bus = info.context.get('bus')
    key = await bus.state_store.store_submission(agent_id=user_id, submission=dataset)
    cmd = SubmitRecords(agent_id=user_id, submission_id=key)
    await bus.handle(cmd)
    return key

@graphql_mutation.field("datasetsUpdateRecords")
@graphql_payload
@require_authentication
async def update_records(
        _,
        info,
        dataset: dict
) -> str:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} updates dataset ID: {dataset.get("dataset_id")}")
    bus = info.context.get('bus')
    key = await bus.state_store.store_submission(agent_id=user_id, submission=dataset)
    cmd = UpdateRecords(agent_id=user_id, submission_id=key)
    await bus.handle(cmd)
    return key

@graphql_mutation.field("datasetsRemoveRecords")
@graphql_payload
@require_authentication
async def remove_records(
        _,
        info,
        dataset_id: int,
        record_ids: List[int]
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} removes records from dataset ID: {dataset_id}")
    bus = info.context.get('bus')
    cmd = RemoveRecords(agent_id=user_id, dataset_id=dataset_id, record_ids=record_ids)
    await bus.handle(cmd)
    return True
