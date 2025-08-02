from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from src.breedgraph.domain.commands.arrangements import CreateLayout
from src.breedgraph.custom_exceptions import UnauthorisedOperationError
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.mutations import graphql_mutation

import logging
logger = logging.getLogger(__name__)

@graphql_mutation.field("create_layout")
@graphql_payload
@require_authentication
async def create_layout(
        _,
        info,
        layout: dict
) -> bool:
    user_id = info.context.get('user_id')
    if user_id is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    logger.debug(f"User {user_id} adding layout: {layout}")

    cmd = CreateLayout(user=user_id, **layout)
    await info.context['bus'].handle(cmd)
    return True
