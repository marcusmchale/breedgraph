from ariadne import ObjectType


from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication

from src.breedgraph.domain.model.datasets import DataSetStored, DataSetOutput, DataRecordStored

from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import (
    update_ontology_map,
    update_units_map
)

from typing import List

import logging
logger = logging.getLogger(__name__)

from . import graphql_query
from ..registry import graphql_resolvers
dataset = ObjectType("DataSet")
record = ObjectType("Record")
graphql_resolvers.register_type_resolvers(dataset, record)

@graphql_query.field("datasets")
@graphql_payload
@require_authentication
async def get_datasets(_, info, dataset: int = None, term: int = None) -> List[DataSetOutput]:
    user = info.context.get('user_id')
    bus = info.context.get('bus')
    async with bus.uow.get_uow(user=user) as uow:
        if dataset is None:
            return [d.to_output() async for d in uow.repositories.datasets.get_all(term=term)]
        else:
            d = uow.repositories.datasets.get(dataset=dataset)
            return [d.to_output()]

#@dataset.field('records')
#async def resolve_records(obj, info):
#    import pdb; pdb.set_trace()
#    pass

@dataset.field('term')
async def resolve_term(obj, info):
    await update_ontology_map(info.context, entry=obj.term)
    ontology = info.context.get('ontology')
    return ontology.to_output(obj.term)

@record.field('unit')
async def resolve_unit(obj, info):
    await update_units_map(info.context, unit=obj.unit)
    units_map = info.context.get('units_map')
    return units_map.get(obj.unit)

