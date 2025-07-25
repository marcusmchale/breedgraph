from ariadne import ObjectType

from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries import graphql_query
from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication

from src.breedgraph.domain.model.datasets import DataSetStored, DataSetOutput, DataRecordStored

from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import (
    inject_ontology,
    update_units_map
)


from typing import List

import logging
logger = logging.getLogger(__name__)

dataset = ObjectType("DataSet")
record = ObjectType("Record")

@graphql_query.field("datasets")
@graphql_payload
@require_authentication
async def get_datasets(_, info, dataset_id: int = None, term_id: int = None) -> List[DataSetOutput]:
    user_id = info.context.get('user_id')
    bus = info.context.get('bus')
    async with bus.uow.get_repositories(user_id=user_id) as uow:
        if dataset_id is None:
            return [d.to_output() async for d in uow.datasets.get_all(term_id=term_id)]
        else:
            d = uow.datasets.get(dataset_id=dataset_id)
            return [d.to_output()]

#@dataset.field('records')
#async def resolve_records(obj, info):
#    import pdb; pdb.set_trace()
#    pass

@dataset.field('term')
async def resolve_term(obj, info):
    await inject_ontology(info.context, entry_id=obj.term)
    ontology = info.context.get('ontology')
    return ontology.to_output(obj.term)

@record.field('unit')
async def resolve_unit(obj, info):
    await update_units_map(info.context, unit_id=obj.unit)
    units_map = info.context.get('units_map')
    return units_map.get(obj.unit)

