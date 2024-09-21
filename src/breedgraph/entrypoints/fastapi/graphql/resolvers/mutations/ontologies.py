from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload
from src.breedgraph.domain.commands.ontologies import AddOntologyEntry

from src.breedgraph.custom_exceptions import UnauthorisedOperationError
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.mutations import graphql_mutation

import logging
logger = logging.getLogger(__name__)

@graphql_mutation.field("ontology_add_entry")
@graphql_payload
async def add_ontology_entry(
        _,
        info,
        entry: dict
) -> bool:
    user_id = info.context.get('user_id')
    if user_id is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    logger.debug(f"User {user_id} adds term: {entry}")
    cmd = AddOntologyEntry(user=user_id, **entry)
    await info.context['bus'].handle(cmd)
    return True
