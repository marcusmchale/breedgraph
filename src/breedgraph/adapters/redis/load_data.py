import csv
from itertools import count

import redis
import json

from pathlib import Path

from src.breedgraph.adapters.neo4j.cypher import queries
from src.breedgraph.domain.model.ontology import OntologyEntryLabel
from src.breedgraph.domain.model.regions import LocationInput, LocationStored
from src.breedgraph.domain.model.ontology.location_type import LocationTypeInput, LocationTypeStored, LocationTypeOutput

# typing only
from neo4j import AsyncResult
from src.breedgraph.service_layer.infrastructure import AbstractUnitOfWork, AbstractUnitHolder

# logging
import logging
logger = logging.getLogger(__name__)

class RedisLoader:

    def __init__(self, connection: redis.Redis, uow: AbstractUnitOfWork):
        self.connection = connection
        self.uow: AbstractUnitOfWork = uow

    async def load_read_model(self, ) -> None:
        # todo rethink this, it it safe to assume the system user is 1?
        # should be, and if not it is only required to create the initial ontology entries anyway
        user_id = 1

        async with self.uow.get_uow(user_id = user_id) as uow:
            await self.load_ontology(uow)
            await self.load_countries(uow)

    async def load_ontology(self, uow: AbstractUnitHolder):
        async for entry in uow.ontology.get_entries(as_output=True):
            await self.connection.hset(
                name=entry.label,
                key=entry.name,
                value=json.dumps(entry.model_dump())
            )
        # create index on the name attribute for each entry.label

    async def load_countries(self, uow: AbstractUnitHolder):
        # get the country type
        country_type = await uow.ontology.get_entry(label=OntologyEntryLabel.LOCATION_TYPE, name="Country")
        if country_type is None:
            country_type = await uow.ontology.create_entry(LocationTypeInput(name="Country"))
        country_type_id = country_type.id

        async for country in uow.views.regions.get_locations_by_type(country_type_id):
            await self.connection.hset(
                name="country",
                key=country.code,
                value=json.dumps(country.model_dump())
            )
        # e.g. https://unstats.un.org/unsd/methodology/m49/overview/
        country_codes_path = Path('src/data/country_codes.csv')
        if country_codes_path.is_file():
            with open(country_codes_path) as country_codes_csv:
                for row in csv.DictReader(country_codes_csv, delimiter=";"):
                    country_input = LocationInput(
                        name=row['Country or Area'],
                        code=row['ISO-alpha3 Code'],
                        type=country_type_id
                    )
                    await self.connection.hsetnx(
                        "country",
                        key=country_input.code,
                        value=json.dumps(country_input.model_dump())
                    )
        else:
            logger.warning("Couldn't find country codes to preload read model")
