from src.breedgraph.domain import commands
from src.breedgraph.domain.model.controls import ReadRelease
from src.breedgraph.domain.model.regions import Region, LocationInput, LocationStored, LocationOutput, GeoCoordinate

from src.breedgraph.adapters.redis.state_store import RedisStateStore
from src.breedgraph.service_layer.infrastructure import AbstractUnitOfWork

from src.breedgraph.custom_exceptions import IdentityExistsError

from ..registry import handlers

import logging
logger = logging.getLogger(__name__)

@handlers.command_handler()
async def create_location(
        cmd: commands.regions.CreateLocation,
        uow: AbstractUnitOfWork,
        state_store: RedisStateStore
):
    if cmd.parent_id is None:
        logger.warning("Root locations must have public read-access, forcing release level to Public")
        release = ReadRelease.PUBLIC
    else:
        release = ReadRelease.PRIVATE

    location_input = LocationInput(
        name = cmd.name,
        fullname = cmd.fullname,
        type = cmd.type_id,
        code = cmd.code,
        address = cmd.address
    )

    async with uow.get_uow(user_id=cmd.agent_id, release=release) as uow:
        if cmd.parent_id is None:
            country = await state_store.get_country(cmd.code)
            if country is None:
                raise ValueError(
                    "Locations without parent must have 3-letter code of Country according to ISO3166."
                )
            elif isinstance(country, LocationOutput):
                raise IdentityExistsError("This country is already stored")

            region = await uow.repositories.regions.create(location_input)
            location = region.root
        else:
            region = await uow.repositories.regions.get(location_id=cmd.parent_id)
            location = region.add_location(location_input, parent_id=cmd.parent_id)

        if cmd.coordinates:
            location.coordinates = [GeoCoordinate(**coord.model_dump()) for coord in cmd.coordinates]
            await uow.repositories.regions.update_seen()

        await uow.commit()


@handlers.command_handler()
async def update_location(
        cmd: commands.regions.UpdateLocation,
        uow: AbstractUnitOfWork
):
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        region = await uow.repositories.regions.get(location_id=cmd.location_id)
        location = region.get_location(cmd.location_id)

        if cmd.name is not None:
            location.name = cmd.name
        if cmd.code is not None:
            location.code = cmd.code
        if cmd.type_id is not None:
            location.type = cmd.type_id
        if cmd.fullname is not None:
            location.fullname = cmd.fullname
        if cmd.description is not None:
            location.description = cmd.description
        if cmd.address is not None:
            location.address = cmd.address
        if cmd.coordinates is not None:
            location.coordinates = [GeoCoordinate(**coord.model_dump()) for coord in cmd.coordinates]
        if cmd.parent_id is not None:
            region.change_source(node_id=cmd.location_id, parent_id=cmd.parent_id)

        await uow.repositories.regions.update_seen()
        await uow.commit()

@handlers.command_handler()
async def delete_location(
        cmd: commands.regions.DeleteLocation,
        uow: AbstractUnitOfWork
):
    async with uow.get_uow(user_id=cmd.agent_id) as uow:
        region = await uow.repositories.regions.get(location_id=cmd.location_id)
        if cmd.location_id == region.root.id:
            await uow.repositories.regions.remove(region)
        else:
            region.remove_location(cmd.location_id)

        await uow.commit()
