import csv
import redis.asyncio as redis
import json

from neo4j import AsyncResult

from pathlib import Path

from src.breedgraph.domain.model.ontology import OntologyEntryLabel, LocationTypeInput
from src.breedgraph.domain.model.regions import LocationInput, LocationOutput

from src.breedgraph.adapters.neo4j.services import Neo4jOntologyPersistenceService
from src.breedgraph.adapters.neo4j.driver import Neo4jAsyncDriver

from src.breedgraph.adapters.neo4j.cypher import queries

# logging
import logging


logger = logging.getLogger(__name__)

class RedisLoader:

    def __init__(self, connection: redis.Redis, driver: Neo4jAsyncDriver):
        self.connection = connection
        self.driver = driver

    async def load_read_model(self, ) -> None:
        await self.load_ontology()
        await self.load_countries()

    async def load_ontology(self):
        async with self.driver.session() as session:
            async with await session.begin_transaction() as tx:
                ontology_service = Neo4jOntologyPersistenceService(tx=tx)
                async for entry in ontology_service.get_entries(as_output=True):
                    await self.connection.hset(
                        name=entry.label,
                        key=entry.name,
                        value=json.dumps(entry.model_dump())
                    )

    async def load_countries(self):
        # get the country type
        async with self.driver.session() as session:
            async with await session.begin_transaction() as tx:
                ontology_service = Neo4jOntologyPersistenceService(tx=tx)
                country_type = await ontology_service.get_entry(
                    label=OntologyEntryLabel.LOCATION_TYPE,
                    name="Country"
                )
                if country_type is None:
                    country_type = await ontology_service.create_entry(
                        LocationTypeInput(name="Country"),
                        # system user
                        user_id=1
                    )
                country_type_id = country_type.id

                result: AsyncResult = await tx.run(
                    queries['regions']['get_locations_by_type_for_read_teams'],
                    location_type=country_type_id,
                    read_teams=[]
                )
                async for record in result:
                    country = LocationOutput(**record['location'])
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
