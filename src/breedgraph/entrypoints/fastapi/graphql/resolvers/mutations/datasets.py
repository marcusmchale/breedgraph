from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload
from src.breedgraph.domain.commands.datasets import (
    AddDataSet,
    AddRecord
)
from src.breedgraph.custom_exceptions import UnauthorisedOperationError
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.mutations import graphql_mutation

from typing import List, Any

import logging
logger = logging.getLogger(__name__)

@graphql_mutation.field("data_add_dataset")
@graphql_payload
async def add_dataset(
        _,
        info,
        term: int
) -> bool:
    user_id = info.context.get('user_id')
    if user_id is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    logger.debug(f"User {user_id} adds dataset for term: {term}")
    cmd = AddDataSet(user=user_id, term=term)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("data_add_record")
@graphql_payload
async def add_record(
        _,
        info,
        record: dict
) -> bool:
    user_id = info.context.get('user_id')
    if user_id is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    logger.debug(f"User {user_id} adds dataset: {record}")

    record_values = list(record.get('value').values())
    if len(record_values) != 1:
        raise ValueError("A single value should be provided per record")
    record['value'] = record_values[0]

    cmd = AddRecord(user=user_id, **record)
    await info.context['bus'].handle(cmd)
    return True
