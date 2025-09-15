from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from src.breedgraph.domain.commands.arrangements import CreateLayout

import logging
logger = logging.getLogger(__name__)

from . import graphql_mutation

@graphql_mutation.field("create_layout")
@graphql_payload
@require_authentication
async def create_layout(
        _,
        info,
        layout: dict
) -> bool:
    user_id: int = info.context.get('user_id')
    logger.debug(f"User {user_id} adding layout: {layout}")
    cmd = CreateLayout(user=user_id, **layout)
    await info.context['bus'].handle(cmd)
    return True
