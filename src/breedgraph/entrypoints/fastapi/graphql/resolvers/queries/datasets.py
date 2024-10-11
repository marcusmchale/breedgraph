from typing import List

import logging
logger = logging.getLogger(__name__)

from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries import graphql_query
from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload

from src.breedgraph.domain.model.datasets import DataSetStored, DataRecordStored

@graphql_query.field("datasets")
@graphql_payload
async def get_datasets(_, info, dataset_id: int = None, term_id: int = None) -> List[DataSetStored]:
    user_id = info.context.get('user_id')
    bus = info.context.get('bus')
    async with bus.uow.get_repositories(user_id=user_id) as uow:
        if dataset_id is None:
            return await uow.datasets.get_all(term_id=term_id)
        else:
            return [uow.datasets.get(dataset_id=dataset_id)]

