from breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload
from breedgraph.entrypoints.fastapi.graphql.acceptances import request_acceptances, save_acceptances

from . import graphql_mutation


@graphql_mutation.field("termsAccept")
@graphql_payload
async def accept_terms(_, info, content_hash: str) -> bool:
    """Accept the current Terms of Use, for the request's user or for a visitor who isn't signed in"""
    if content_hash != info.context['terms_of_use'].content_hash:
        raise ValueError("The Terms of Use have changed: please read them again")
    acceptances = request_acceptances(info.context)
    acceptances.terms = content_hash
    save_acceptances(info.context, acceptances)
    return True
