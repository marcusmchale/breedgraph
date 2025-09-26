from src.breedgraph.domain.model.controls import ReadRelease
from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from src.breedgraph.domain.commands.arrangements import CreateLayout

import logging
logger = logging.getLogger(__name__)

from . import graphql_mutation

@graphql_mutation.field("arrangementsCreateLayout")
@graphql_payload
@require_authentication
async def create_layout(
        _,
        info,
        layout: dict
) -> bool:
    user_id: int = info.context.get('user_id')
    logger.debug(f"User {user_id} adding layout: {layout}")
    cmd = CreateLayout(
        agent_id = user_id,
        name = layout.get('name'),
        type_id = layout.get('type_id'),
        location_id= layout.get('location_id'),
        axes = layout.get('axes'),
        parent = layout.get('parent_id'),
        position = layout.get('position')
    )
    await info.context['bus'].handle(cmd)
    return True
