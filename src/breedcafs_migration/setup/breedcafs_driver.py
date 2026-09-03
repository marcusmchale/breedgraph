from neo4j import AsyncGraphDatabase, AsyncDriver

from breedgraph.service_layer.infrastructure.driver import AbstractAsyncDriver

from .config import BREEDCAFS_DB_HOST, BREEDCAFS_DB_NAME, BREEDCAFS_DB_PORT, BREEDCAFS_NEO4J_PASSWORD, BREEDCAFS_NEO4J_USERNAME

class BreedCAFSAsyncDriver(AbstractAsyncDriver):
    def __init__(self):
        self.driver: AsyncDriver = AsyncGraphDatabase.driver(
            f"neo4j://{BREEDCAFS_DB_HOST}:{BREEDCAFS_DB_PORT}",
            auth=(BREEDCAFS_NEO4J_USERNAME, BREEDCAFS_NEO4J_PASSWORD),
            database=BREEDCAFS_DB_NAME
        )

    def session(self):
        return self.driver.session()

    async def close(self):
        await self.driver.close()


