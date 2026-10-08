from breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from breedgraph.domain.model.controls import ControlledModelLabel, ReadRelease
from breedgraph.domain.commands.controls import SetRelease
from breedgraph.domain.commands.control_transfers import (
    OfferControlTransfer, AcceptControlTransfer, RejectControlTransfer, CancelControlTransfer, RenounceControl
)

from typing import List

import logging
logger = logging.getLogger(__name__)

from . import graphql_mutation

@graphql_mutation.field("controlsSetRelease")
@graphql_payload
@require_authentication
async def set_release(
        _,
        info,
        entity_ids: List[int],
        entity_label: ControlledModelLabel,
        release: ReadRelease,
) -> bool:

    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} sets controls for {entity_label}: {entity_ids} to {release.value}")
    cmd = SetRelease(agent_id=user_id, entity_ids=entity_ids, entity_label=entity_label, release=release)
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("controlsOfferTransfer")
@graphql_payload
@require_authentication
async def offer_transfer(_, info, offer: dict) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} offers control transfer to team {offer.get('recipient_team_id')}")
    cmd = OfferControlTransfer(
        agent_id=user_id,
        entities=offer['entities'],
        from_teams=offer['from_team_ids'],
        recipient_team=offer['recipient_team_id'],
        keep_from_teams=offer.get('keep_from_teams') or False,
        to_teams=offer.get('to_team_ids'),
        release=offer.get('release') or ReadRelease.PRIVATE
    )
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("controlsAcceptTransfer")
@graphql_payload
@require_authentication
async def accept_transfer(_, info, id: int, to_team_ids: List[int], release: ReadRelease | None = None) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} accepts control transfer {id}")
    cmd = AcceptControlTransfer(
        agent_id=user_id,
        transfer_id=id,
        to_teams=to_team_ids,
        release=release or ReadRelease.PRIVATE
    )
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("controlsRejectTransfer")
@graphql_payload
@require_authentication
async def reject_transfer(_, info, id: int) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} rejects control transfer {id}")
    await info.context['bus'].handle(RejectControlTransfer(agent_id=user_id, transfer_id=id))
    return True

@graphql_mutation.field("controlsCancelTransfer")
@graphql_payload
@require_authentication
async def cancel_transfer(_, info, id: int) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} cancels control transfer {id}")
    await info.context['bus'].handle(CancelControlTransfer(agent_id=user_id, transfer_id=id))
    return True

@graphql_mutation.field("controlsRenounceControl")
@graphql_payload
@require_authentication
async def renounce_control(_, info, entities: List[dict], team_ids: List[int]) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} renounces control for teams {team_ids}")
    await info.context['bus'].handle(RenounceControl(agent_id=user_id, entities=entities, team_ids=team_ids))
    return True
