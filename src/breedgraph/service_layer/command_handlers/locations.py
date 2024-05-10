import re

from src.breedgraph.adapters.redis.read_model import ReadModel
from src.breedgraph.custom_exceptions import UnauthorisedOperationError
from src.breedgraph.domain import commands
from src.breedgraph.domain.model.accounts import Access, Authorisation
from src.breedgraph.domain.model.locations import Country

from src.breedgraph.views.locations import countries

from src.breedgraph.service_layer import unit_of_work


async def add_country(
        cmd: commands.accounts.AddCountry,
        uow: unit_of_work.AbstractUnitOfWork,
        read_model: ReadModel
):
    async with uow:
        admin = await uow.accounts.get(cmd.admin)

        for a in admin.affiliations:
            if a.access == Access.ADMIN and a.authorisation == Authorisation.AUTHORISED:
               break
        else:
            raise UnauthorisedOperationError("Only admins can add a country")

        country = Country(
            name=cmd.name,
            code=cmd.code
        )

        # here we check the read model as it includes pre-cached and valid but not stored values for country
        async for c in read_model.get_countries():
            if c == country:
                break
        else:
            # if it isn't in the read model, it can only be added if it is valid for custom user codes
            # https://www.iso.org/glossary-for-iso-3166.html
            # AAA to AAZ, QMA to QZZ, XAA to XZZ, and ZZA to ZZZ
            if not len(cmd.code) == 3 and any([
                re.match('AA[A-Z]', cmd.code),
                re.match('Q[M-Z][A-Z]', cmd.code),
                re.match('X[A-Z][A-Z]', cmd.code),
                re.match('ZZ[A-Z]', cmd.code),
            ]):
                raise TypeError('Invalid country code - must be an iso3166 alpha3 user-assigned code')


        account.affiliations.append(
                Affiliation(
                    team=stored_team.id,
                    access=Access.ADMIN,
                    authorisation=Authorisation.AUTHORISED
                )
        )
        await uow.commit()