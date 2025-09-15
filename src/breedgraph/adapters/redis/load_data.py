import csv
from itertools import count

import redis
import json

from pathlib import Path

from src.breedgraph.adapters.neo4j.cypher import queries
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

    async def load_read_model(self, user_id:int = None) -> None:
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
        country_type_id = None
        entries_json = await self.connection.hgetall("LocationType")
        for entry_json in entries_json.values():
            entry_data = json.loads(entry_json)
            if entry_data.get('name') == "Country":
                country_type_id = entry_data.get('id')
                break
        async for country in uow.views.get_countries():
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
