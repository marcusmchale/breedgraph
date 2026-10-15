from ariadne import ObjectType, EnumType

from breedgraph.domain.model.time_descriptors import WriteStamp
from breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import (
    update_teams_map,
    update_users_map,
    team_references,
    get_context_views,
    get_context_lock
)

from breedgraph.domain.model.controls import ControlledModel, Controller, ControlledModelLabel, Control, Access
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
    """
    Through the controls view: an entity the user cannot read has a placeholder controller, its controls without the
    writes to it (see docs/read-access.md). Only for signed-in users, who can ask for access.
    """
    user_id = info.context.get('user_id')
    bus = info.context.get('bus')
    async with bus.uow_factory.get_uow(user_id=user_id) as uow:
        # for Controller.access, which answers from the user's affiliations rather than the teams they can see
        info.context['access_teams'] = {access: set(teams) for access, teams in uow.controls.access_teams.items()}
    async with get_context_lock(info.context):
        views = await get_context_views(info.context)
        controllers = await views.controls.get_controllers(entity_label, entity_ids)
    return [controllers.get(int(entity_id)) for entity_id in entity_ids]


@controller.field("access")
def resolve_access(obj: Controller, info) -> List[Access]:
    """What the user's affiliations let them do with the entity through the teams that control it"""
    user_id = info.context.get('user_id')
    access_teams = info.context.get('access_teams', {})
    return [access for access in Access if obj.has_access(access, user_id, access_teams.get(access, set()))]

@controller.field("controls")
async def resolve_controls(obj: Controller, info):
    """Resolve controls field on Controller, loading their teams in one call"""
    await update_teams_map(context=info.context, team_ids=[control.team_id for control in obj.controls.values()])
    return obj.controls.values()

@controller.field("writes")
async def resolve_writes(obj: Controller, info, last: int | None = None) -> List[WriteStamp]:
    """The writes in the order they were made, or the last of them, loading their users in one call"""
    writes = obj.writes if last is None else obj.writes[-last:] if last > 0 else []
    await update_users_map(context=info.context, user_ids={write.user for write in writes})
    return writes

@controller.field("writeCount")
def resolve_write_count(obj: Controller, info) -> int:
    return len(obj.writes)

@control.field("team")
async def resolve_team(obj: Control, info):
    """The controlling team, or the team standing in for it when it is hidden from the user"""
    references = await team_references(info.context, [obj.team_id])
    return references[0] if references else None

@control.field("time")
async def resolve_time(obj: Control, info) -> str | None:
    return str(obj.time) if obj.time is not None else None

@controller.field("teams")
async def resolve_teams(obj: Controller, info):
    """The controlling teams, those hidden from the user stood in for by the nearest team they can see"""
    return await team_references(info.context, obj.teams)

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
    # none for a placeholder controller, which has no writes
    return str(obj.created) if obj.writes else None

@controller.field("updated")
async def resolve_updated(obj: Controller, info):
    return str(obj.updated) if obj.writes else None

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
