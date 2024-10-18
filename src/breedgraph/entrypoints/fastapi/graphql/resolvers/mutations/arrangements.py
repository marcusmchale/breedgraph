from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload
from src.breedgraph.domain.commands.arrangements import AddLayout
from src.breedgraph.custom_exceptions import UnauthorisedOperationError
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.mutations import graphql_mutation

import logging
logger = logging.getLogger(__name__)

@graphql_mutation.field("add_layout")
@graphql_payload
async def add_layout(
        _,
        info,
        layout: dict
) -> bool:
    user_id = info.context.get('user_id')
    if user_id is None:
        raise UnauthorisedOperationError("Please provide a valid token")

    logger.debug(f"User {user_id} adding layout: {layout}")

    cmd = AddLayout(user=user_id, **layout)
    await info.context['bus'].handle(cmd)
    return True
