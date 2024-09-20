from typing import List

from src.breedgraph.views.regions import countries  # todo consider injection into context per accounts/teams

from src.breedgraph.domain.model.regions import LocationBase
from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload

from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries import graphql_query

@graphql_query.field("countries")
@graphql_payload
async def get_countries(_, info) -> List[LocationBase]:
    bus = info.context.get('bus')
    return [c async for c in countries(bus.read_model)]
