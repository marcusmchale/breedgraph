import asyncio

from typing import List

from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from src.breedgraph.domain.commands.datasets import (
    CreateDataset,
    UpdateDataset,
    AddRecords,
    RemoveRecords
)

import logging
logger = logging.getLogger(__name__)

from . import graphql_mutation


@graphql_mutation.field("datasetsCreateDataset")
@graphql_payload
@require_authentication
async def create_dataset(
        _,
        info,
        dataset: dict
) -> str:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} adds dataset for concept: {dataset.get("concept_id")}")
    bus = info.context.get('bus')
    key = await bus.state_store.store_submission(agent_id=user_id, submission=dataset)
    cmd = CreateDataset(agent_id=user_id, submission_id=key)
    asyncio.create_task(info.context['bus'].handle(cmd))
    return key

@graphql_mutation.field("datasetsUpdateDataset")
@graphql_payload
@require_authentication
async def update_dataset(
        _,
        info,
        dataset: dict
) -> str:
    user_id = info.context.get('user_id')
    bus = info.context.get('bus')
    key = await bus.state_store.store_submission(agent_id=user_id, submission=dataset)
    logger.debug(f"User {user_id} updates dataset ID: {dataset.get("dataset_id")}")
    cmd = UpdateDataset(agent_id=user_id, key=key)
    asyncio.create_task(info.context['bus'].handle(cmd))
    return key

@graphql_mutation.field("datasetsAddRecords")
@graphql_payload
@require_authentication
async def add_records(
        _,
        info,
        dataset_id: int,
        records: List[dict]
) -> str:
    user_id = info.context.get('user_id')
    bus = info.context.get('bus')
    key = await bus.state_store.store_submission(agent_id=user_id, submission={"dataset_id": dataset_id, "records": records})
    logger.debug(f"User {user_id} adds records to dataset ID: {dataset_id}")
    cmd = AddRecords(agent_id=user_id, key=key)
    asyncio.create_task(info.context['bus'].handle(cmd))
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
    cmd = RemoveRecords(agent_id=user_id, dataset_id=dataset_id, record_ids=record_ids)
    await info.context['bus'].handle(cmd)
    return True
