from ariadne import ObjectType, EnumType

from breedgraph.domain.model.time_descriptors import WriteStamp
from breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import (
    update_teams_map,
    update_users_map
)

from breedgraph.domain.model.controls import ControlledModel, Controller, ControlledModelLabel, Control
from breedgraph.domain.model.control_transfers import ControlTransferStored, ControlTransferStatus
from breedgraph.custom_exceptions import NoResultFoundError

import logging
logger = logging.getLogger(__name__)

from . import graphql_query
from ..registry import graphql_resolvers

from typing import List

controller = ObjectType("Controller")
control = ObjectType("Control")
write_stamp = ObjectType("WriteStamp")
graphql_resolvers.register_type_resolvers(controller, control, write_stamp)
control_transfer = ObjectType("ControlTransfer")
graphql_resolvers.register_type_resolvers(control_transfer)
graphql_resolvers.register_enums(EnumType("ControlledModelLabel", ControlledModelLabel))
graphql_resolvers.register_enums(EnumType("ControlTransferStatus", ControlTransferStatus))

@graphql_query.field("controlsControllers")
@graphql_payload
@require_authentication
async def get_controllers(_, info, entity_label: ControlledModelLabel, entity_ids: List[int]) -> List[Controller]:
    user_id = info.context.get('user_id')
    bus = info.context.get('bus')
    async with bus.uow_factory.get_uow(user_id=user_id) as uow:
        controllers = await uow.controls.get_controllers(label=entity_label, model_ids=entity_ids)
        return [controllers.get(entity_id) for entity_id in entity_ids]

@controller.field("controls")
def resolve_controls(obj: Controller, info):
    """Resolve controls field on Controller"""
    return obj.controls.values()

@control.field("team")
async def resolve_team(obj: Control, info):
    await update_teams_map(context = info.context, team_ids = [obj.team_id])
    teams_map = info.context.get('teams_map', {})
    return teams_map.get(obj.team_id)

@control.field("time")
async def resolve_time(obj: WriteStamp, info) -> str:
    return str(obj.time)

@controller.field("teams")
async def resolve_teams(obj: Controller, info):
    """Resolve teams field on Controller"""
    await update_teams_map(context = info.context, team_ids=obj.teams)
    teams_map = info.context.get('teams_map', {})
    return [teams_map.get(team) for team in obj.teams if teams_map.get(team)]

@write_stamp.field("user")
async def resolve_user(obj: WriteStamp, info):
    await update_users_map(context=info.context, user_ids=[obj.user])
    users_map = info.context.get('users_map', {})
    return users_map.get(obj.user)

@write_stamp.field("time")
async def resolve_time(obj: WriteStamp, info) -> str:
    return str(obj.time)

@controller.field("created")
async def resolve_created(obj: Controller, info):
    return str(obj.created)

@controller.field("updated")
async def resolve_updated(obj: Controller, info):
    return str(obj.updated)

@graphql_query.field("controlsTransfers")
@graphql_payload
@require_authentication
async def get_transfers(_, info, statuses: List[ControlTransferStatus] | None = None) -> List[ControlTransferStored]:
    user_id = info.context.get('user_id')
    bus = info.context.get('bus')
    async with bus.uow_factory.get_uow(user_id=user_id) as uow:
        return await uow.controls.get_transfers(statuses=statuses)

@graphql_query.field("controlsTransfer")
@graphql_payload
@require_authentication
async def get_transfer(_, info, id: int) -> ControlTransferStored:
    user_id = info.context.get('user_id')
    bus = info.context.get('bus')
    async with bus.uow_factory.get_uow(user_id=user_id) as uow:
        transfer = await uow.controls.get_transfer(id)
    if transfer is None:
        raise NoResultFoundError(f"Control transfer {id} not found")
    return transfer

async def _resolve_teams(info, team_ids):
    await update_teams_map(context=info.context, team_ids=team_ids)
    teams_map = info.context.get('teams_map', {})
    return [teams_map.get(team_id) for team_id in team_ids if teams_map.get(team_id)]

async def _resolve_user(info, user_id):
    if user_id is None:
        return None
    await update_users_map(context=info.context, user_ids=[user_id])
    return info.context.get('users_map', {}).get(user_id)

@control_transfer.field("fromTeams")
async def resolve_from_teams(obj: ControlTransferStored, info):
    return await _resolve_teams(info, obj.from_teams)

@control_transfer.field("toTeams")
async def resolve_to_teams(obj: ControlTransferStored, info):
    return await _resolve_teams(info, obj.to_teams)

@control_transfer.field("recipientTeam")
async def resolve_recipient_team(obj: ControlTransferStored, info):
    teams = await _resolve_teams(info, [obj.recipient_team])
    return teams[0] if teams else None

@control_transfer.field("offeredBy")
async def resolve_offered_by(obj: ControlTransferStored, info):
    return await _resolve_user(info, obj.offered_by)

@control_transfer.field("acceptedBy")
async def resolve_accepted_by(obj: ControlTransferStored, info):
    return await _resolve_user(info, obj.accepted_by)

@control_transfer.field("rejectedBy")
async def resolve_rejected_by(obj: ControlTransferStored, info):
    return await _resolve_user(info, obj.rejected_by)

@control_transfer.field("cancelledBy")
async def resolve_cancelled_by(obj: ControlTransferStored, info):
    return await _resolve_user(info, obj.cancelled_by)
