from neo4j import AsyncGraphDatabase, AsyncDriver
from src.breedgraph.service_layer.infrastructure.driver import AbstractAsyncDriver

from src.breedgraph.config import get_bolt_url, get_graphdb_auth, DATABASE_NAME

class Neo4jAsyncDriver(AbstractAsyncDriver):
    def __init__(self):
        self.driver: AsyncDriver = AsyncGraphDatabase.driver(
            get_bolt_url(),
            auth=get_graphdb_auth(),
            database=DATABASE_NAME,
            connection_timeout=5,
            connection_acquisition_timeout=5,
            max_transaction_retry_time=5
        )

    def session(self):
        return self.driver.session()

    async def close(self):
        await self.driver.close()


