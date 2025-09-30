from ariadne import ObjectType

from src.breedgraph.domain.model.time_descriptors import WriteStamp
from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import (
    update_teams_map,
    update_users_map
)

from src.breedgraph.domain.model.controls import ControlledModel, Controller, ControlledModelLabel, Control

import logging
logger = logging.getLogger(__name__)

from . import graphql_query
from ..registry import graphql_resolvers

from typing import List

controller = ObjectType("Controller")
control = ObjectType("Control")
write_stamp = ObjectType("WriteStamp")
graphql_resolvers.register_type_resolvers(controller, control, write_stamp)
graphql_resolvers.register_enums(ControlledModelLabel)

@graphql_query.field("controlsControllers")
@graphql_payload
@require_authentication
async def get_controllers(_, info, entity_label: ControlledModelLabel, entity_ids: List[int]) -> List[Controller]:
    user_id = info.context.get('user_id')
    bus = info.context.get('bus')
    async with bus.uow.get_uow(user_id=user_id) as uow:
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