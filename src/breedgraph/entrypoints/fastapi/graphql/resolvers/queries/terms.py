from breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload
from breedgraph.entrypoints.fastapi.graphql.acceptances import terms_accepted

from . import graphql_query


@graphql_query.field("termsOfUse")
@graphql_payload
async def get_terms_of_use(_, info) -> dict:
    terms = info.context['terms_of_use']
    return {'text': terms.text, 'content_hash': terms.content_hash, 'accepted': terms_accepted(info.context)}
