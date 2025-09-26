from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from src.breedgraph.domain.commands.regions import CreateLocation
from src.breedgraph.custom_exceptions import UnauthorisedOperationError
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.mutations import graphql_mutation

import logging
logger = logging.getLogger(__name__)

@graphql_mutation.field("regionsCreateLocation")
@graphql_payload
@require_authentication
async def create_location(
        _,
        info,
        location: dict
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} adding location: {location}")
    cmd = CreateLocation(
        agent_id=user_id, **location
    )
    await info.context['bus'].handle(cmd)
    return True
