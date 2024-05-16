import csv
import redis

from pathlib import Path

from src.breedgraph.adapters.neo4j.cypher import queries
from src.breedgraph.domain.model.locations import Location, Region

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
        async with self.uow as uow:
            result: AsyncResult = await uow.tx.run(queries['get_countries'])
            async for record in result:
                country = Region(**record['country'])
                await self.connection.sadd("country", country.model_dump_json())

        # e.g. https://unstats.un.org/unsd/methodology/m49/overview/
        country_codes_path = Path('src/data/country_codes.csv')
        #todo get code for country LocationType, or just assume is 0?
        if country_codes_path.is_file():
            with open(country_codes_path) as country_codes_csv:
                for row in csv.DictReader(country_codes_csv, delimiter=";"):
                    location = Location(name=row['Country or Area'], code=row['ISO-alpha3 Code'], type=None)
                    country = Region(locations=[location])
                    await self.connection.sadd("country", country.model_dump_json())
        else:
            logger.warning("Couldn't find country codes to preload read model")
