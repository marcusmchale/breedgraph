from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from src.breedgraph.domain.commands.datasets import (
    CreateDataSet,
    AddRecord
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
        concept_id: int
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} adds dataset for ontology entry: {concept_id}")
    cmd = CreateDataSet(agent_id=user_id, concept_id=concept_id)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("datasetsAddRecord")
@graphql_payload
@require_authentication
async def add_record(
        _,
        info,
        record: dict
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} adds record: {record}")
    cmd = AddRecord(agent_id=user_id, **record)
    await info.context['bus'].handle(cmd)
    return True
