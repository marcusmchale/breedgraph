from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from src.breedgraph.domain.model.controls import ControlledModelLabel, ReadRelease
from src.breedgraph.domain.commands.controls import SetControls

from typing import List

import logging
logger = logging.getLogger(__name__)

from . import graphql_mutation

@graphql_mutation.field("controlsSetControls")
@graphql_payload
@require_authentication
async def set_controls(
        _,
        info,
        entity_ids: List[int],
        entity_label: ControlledModelLabel,
        release: ReadRelease
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} sets controls for {entity_label}: {entity_ids} to {release.value}")
    cmd = SetControls(agent_id=user_id, entity_ids=entity_ids, entity_label=entity_label, release=release)
    await info.context['bus'].handle(cmd)
    return True