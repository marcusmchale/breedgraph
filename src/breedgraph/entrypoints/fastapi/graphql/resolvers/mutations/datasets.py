from typing import List

from breedgraph.domain.model import DatasetInput
from breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from breedgraph.domain.commands.datasets import (
    CreateDataset,
    UpdateDataset,
    AddRecords,
    RemoveRecords
)

import logging
logger = logging.getLogger(__name__)

from . import graphql_mutation


@graphql_mutation.field("datasetsCreate")
@graphql_payload
@require_authentication
async def create_dataset(
        _,
        info,
        dataset: dict,
        control_team_id: int | None = None
) -> str:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} adds dataset for concept: {dataset.get('concept_id')}")
    bus = info.context.get('bus')
    key = await bus.state_store.store_submission(agent_id=user_id, submission=dataset)
    cmd = CreateDataset(agent_id=user_id, write_team=control_team_id, submission_id=key)
    await bus.handle(cmd)
    return key

@graphql_mutation.field("datasetsUpdate")
@graphql_payload
@require_authentication
async def update_dataset(
        _,
        info,
        dataset: dict
) -> str:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} updates dataset ID: {dataset.get("id")}")
    bus = info.context.get('bus')
    dataset['dataset_id'] = dataset.pop('id')
    key = await bus.state_store.store_submission(agent_id=user_id, submission=dataset)
    cmd = UpdateDataset(agent_id=user_id, submission_id=key)
    await bus.handle(cmd)
    return key


@graphql_mutation.field("datasetsAddRecords")
@graphql_payload
@require_authentication
async def add_records(
        _,
        info,
        id: int,
        records: list[dict]
) -> str:
    user_id = info.context.get('user_id')

    logger.debug(f"User {user_id} adds records to dataset {id}")
    bus = info.context.get('bus')
    key = await bus.state_store.store_submission(agent_id=user_id, submission={
        "dataset_id": id,
        "records": records
    })
    cmd = AddRecords(agent_id=user_id, submission_id=key)
    await bus.handle(cmd)
    return key


@graphql_mutation.field("datasetsRemoveRecords")
@graphql_payload
@require_authentication
async def remove_records(
        _,
        info,
        id: int,
        record_ids: List[int]
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} removes records from dataset ID: {id}")
    bus = info.context.get('bus')
    cmd = RemoveRecords(agent_id=user_id, dataset_id=id, record_ids=record_ids)
    await bus.handle(cmd)
    return True
