from breedgraph.domain.model.controls import ReadRelease
from breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from breedgraph.domain.commands.germplasm import (
    CreateGermplasm, UpdateGermplasm, DeleteGermplasm
)
import logging
logger = logging.getLogger(__name__)

from . import graphql_mutation

@graphql_mutation.field("germplasmCreateEntry")
@graphql_payload
@require_authentication
async def create_entry(
        _, info,
        entry: dict,
        control_team_id: int | None = None,
        release: ReadRelease = ReadRelease.PRIVATE
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} creates germplasm entry: {entry}")
    cmd = CreateGermplasm(agent_id=user_id, write_team=control_team_id, release=release, **entry)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("germplasmUpdateEntry")
@graphql_payload
@require_authentication
async def update_entry(_, info, entry: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} updates germplasm entry: {entry}")
    entry['germplasm_id'] = entry.pop('id')
    cmd = UpdateGermplasm(agent_id=user_id, **entry)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("germplasmDeleteEntry")
@graphql_payload
@require_authentication
async def delete_entry(_, info, id: int) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} deletes germplasm entry: {id}")
    cmd = DeleteGermplasm(agent_id=user_id, germplasm_id=id)
    await info.context['bus'].handle(cmd)
    return True
