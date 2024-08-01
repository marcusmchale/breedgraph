import re

from src.breedgraph.adapters.redis.read_model import ReadModel
from src.breedgraph.custom_exceptions import UnauthorisedOperationError
from src.breedgraph.domain import commands
from src.breedgraph.domain.model.organisations import Access, Authorisation
from src.breedgraph.domain.model.regions import Region, LocationInput, LocationStored



from src.breedgraph.service_layer import unit_of_work


async def add_location(
        cmd: commands.regions.AddLocation,
        uow: unit_of_work.AbstractUnitOfWork,
        read_model: ReadModel
):
    async with uow.get_repositories() as uow:
        user = await uow.accounts.get(cmd.user)
        import pdb; pdb.set_trace()
        region = Region(nodes=LocationInput(**cmd.model_dump()))
        import pdb; pdb.set_trace()
        # here we check the read model as it includes pre-cached and valid but not stored values for country
        #async for c in read_model.get_countries():
        #    if c == country:
        #        break
        #else:
        #    # if it isn't in the read model, it can only be added if it is valid for custom user codes
        #    # https://www.iso.org/glossary-for-iso-3166.html
        #    # AAA to AAZ, QMA to QZZ, XAA to XZZ, and ZZA to ZZZ
        #    if not len(cmd.code) == 3 and any([
        #        re.match('AA[A-Z]', cmd.code),
        #        re.match('Q[M-Z][A-Z]', cmd.code),
        #        re.match('X[A-Z][A-Z]', cmd.code),
        #        re.match('ZZ[A-Z]', cmd.code),
        #    ]):
        #        raise TypeError('Invalid country code - must be an iso3166 alpha3 user-assigned code')


        await uow.commit()