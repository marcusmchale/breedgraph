import logging
from src.breedgraph.adapters.redis.read_model import ReadModel

from src.breedgraph.domain import commands
from src.breedgraph.domain.model.controls import ReadRelease
from src.breedgraph.domain.model.regions import Region, LocationInput, LocationStored, LocationOutput

from src.breedgraph.custom_exceptions import IdentityExistsError

from src.breedgraph.service_layer import unit_of_work

logger = logging.getLogger(__name__)

async def add_location(
        cmd: commands.regions.AddLocation,
        uow: unit_of_work.AbstractUnitOfWork,
        read_model: ReadModel
):
    if cmd.parent is None and not cmd.release == "PUBLIC":
        logger.warning("Root locations must have public read-access, changing release value")
        cmd.release = "PUBLIC"

    async with uow.get_repositories(user_id=cmd.user, release=ReadRelease[cmd.release]) as uow:
        if cmd.parent is None:
            country = read_model.get_country(cmd.code)
            if country is None:
                raise ValueError(
                    "Locations without parent must have 3-letter code of Country according to ISO3166."
                )
            elif isinstance(country, LocationOutput):
                raise IdentityExistsError("This country is already stored")

            location_input = LocationInput(**cmd.model_dump())
            await uow.regions.create(location_input)
        else:
            region = await uow.regions.get(location_id=cmd.parent)
            region.add_location(LocationInput(**cmd.model_dump()), parent_id=cmd.parent)
        await uow.commit()
