from breedgraph.domain.model.controls import ReadRelease
from breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from breedgraph.domain.commands.regions import CreateLocation, UpdateLocation, DeleteLocation
from breedgraph.custom_exceptions import UnauthorisedOperationError
from breedgraph.entrypoints.fastapi.graphql.resolvers.mutations import graphql_mutation

import logging
logger = logging.getLogger(__name__)

@graphql_mutation.field("regionsCreateLocation")
@graphql_payload
@require_authentication
async def create_location(
        _,
        info,
        location: dict,
        control_team_id: int | None = None,
        release: ReadRelease = ReadRelease.PRIVATE
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} adding location: {location}")
    cmd = CreateLocation(
        agent_id=user_id, write_team=control_team_id, release=release, **location
    )
    await info.context['bus'].handle(cmd)
    return True

@graphql_mutation.field("regionsUpdateLocation")
@graphql_payload
@require_authentication
async def update_location(
        _,
        info,
        location: dict
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} updating location: {location}")
    location['location_id'] = location.pop('id')
    cmd = UpdateLocation(
        agent_id=user_id, **location
    )
    await info.context['bus'].handle(cmd)
    return True


@graphql_mutation.field("regionsDeleteLocation")
@graphql_payload
@require_authentication
async def delete_location(
        _,
        info,
        id: int
) -> bool:
    user_id = info.context.get('user_id')
    logger.debug(f"User {user_id} deleting location: {id}")
    cmd = DeleteLocation(
        agent_id=user_id, location_id=id
    )
    await info.context['bus'].handle(cmd)
    return True
