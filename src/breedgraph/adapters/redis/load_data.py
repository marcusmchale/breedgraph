import csv
import redis

from pathlib import Path

from src.breedgraph.adapters.neo4j.cypher import queries
from src.breedgraph.domain.model.regions import LocationInput, LocationStored, Region
from src.breedgraph.domain.model.ontology.locations import Location
from src.breedgraph.domain.model.controls import Controller

# typing only
from neo4j import AsyncResult
from src.breedgraph.service_layer.unit_of_work import Neo4jUnitOfWork

# logging
import logging
logger = logging.getLogger(__name__)

class RedisLoader:

    def __init__(self, connection: redis.Redis):
        self.connection = connection
        self.uow = Neo4jUnitOfWork()

    async def load_read_model(self) -> None:
        await self.load_countries()

    async def load_countries(self, ):
        async with self.uow.get_repositories() as uow:
            ontology = await uow.ontologies.get()
            if next(ontology.get_by_name_and_label(name='Country', label='LocationType'), None) is None:
                ontology._add_entry(
                    Location(
                        name='Country',
                        description='Country and three digit code according to ISO 3166-1 alpha-3'
                    )
                )
                await uow.ontologies.update_seen()
                ontology = await uow.ontologies.get()
            country_type = next(ontology.get_by_name_and_label(name='Country', label='LocationType'))
            result: AsyncResult = await uow.tx.run(queries['regions']['get_locations_by_type'], type=country_type.id)
            async for record in result:
                location_stored = LocationStored(**record['location'])
                await self.connection.sadd("country", location_stored.model_dump_json())

        # e.g. https://unstats.un.org/unsd/methodology/m49/overview/
        country_codes_path = Path('src/data/country_codes.csv')
        #todo get code for country LocationType, or just assume is 0?
        if country_codes_path.is_file():
            with open(country_codes_path) as country_codes_csv:
                for row in csv.DictReader(country_codes_csv, delimiter=";"):
                    location_input = LocationInput(
                        name=row['Country or Area'],
                        code=row['ISO-alpha3 Code'],
                        type=country_type.id,
                        controller=Controller(controls=[])
                    )
                    await self.connection.sadd("country", location_input.model_dump_json())
        else:
            logger.warning("Couldn't find country codes to preload read model")
