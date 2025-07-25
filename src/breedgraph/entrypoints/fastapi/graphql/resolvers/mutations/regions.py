from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from src.breedgraph.domain.commands.regions import AddLocation
from src.breedgraph.custom_exceptions import UnauthorisedOperationError
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.mutations import graphql_mutation

import logging
logger = logging.getLogger(__name__)

@graphql_mutation.field("add_location")
@graphql_payload
@require_authentication
async def add_location(
        _,
        info,
        location: dict
) -> bool:
    user_id = info.context.get('user_id')
    if user_id is None:
        raise UnauthorisedOperationError("Please provide a valid token")
    logger.debug(f"User {user_id} adding location: {location}")
    cmd = AddLocation(user=user_id, **location)
    await info.context['bus'].handle(cmd)
    return True
