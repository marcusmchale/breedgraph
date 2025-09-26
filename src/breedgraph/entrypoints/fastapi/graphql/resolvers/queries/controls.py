from ariadne import ObjectType

from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import (
    update_teams_map,
    update_users_map
)

from src.breedgraph.domain.model.controls import ControlledModel, Controller

import logging
logger = logging.getLogger(__name__)

from . import graphql_query
from ..registry import graphql_resolvers

controller = ObjectType("Controller")
control = ObjectType("Control")
write_stamp = ObjectType("WriteStamp")
graphql_resolvers.register_type_resolvers(controller, control, write_stamp)


async def resolve_controller(obj: ControlledModel, info) -> Controller:
    await update_teams_map(info.context, obj.controller.teams)
    write_users = [w.user for w in obj.controller.writes]
    await update_users_map(info.context, write_users)
    return obj.controller

# Shared field resolvers for Controller type
@controller.field("controls")
def resolve_controls(obj: Controller, info):
    """Resolve controls field on Controller"""
    return [{'team': key, **value.model_dump()} for key, value in obj.controls.items()]

@control.field("team")
def resolve_team(obj: dict, info):
    teams_map = info.context.get('teams_map', {})
    return teams_map.get(obj.get('team'))

@controller.field("writes")
def resolve_writes(obj, info):
    import pdb; pdb.set_trace()
    """Resolve writes field on Controller"""
    return obj.writes

@controller.field("teams")
def resolve_teams(obj: Controller, info):
    """Resolve teams field on Controller"""
    teams_map = info.context.get('teams_map', {})
    return [teams_map.get(team) for team in obj.teams if teams_map.get(team)]

@controller.field("release")
def resolve_release(obj: Controller, info):
    """Resolve release field on Controller"""
    return obj.release

@controller.field("created")
def resolve_created(obj: Controller, info):
    """Resolve created field on Controller"""
    return obj.created

@controller.field("updated")
def resolve_updated(obj: Controller, info):
    """Resolve updated field on Controller"""
    return obj.updated

