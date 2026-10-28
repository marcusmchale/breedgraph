from neo4j import AsyncGraphDatabase, AsyncDriver, NotificationClassification
from breedgraph.service_layer.infrastructure.driver import AbstractAsyncDriver

from breedgraph.config import get_bolt_url, get_graphdb_auth, DATABASE_NAME

# The Cypher the queries are written in (coll.distinct, coll.flatten, scoped CALL subqueries). A database runs the
# language it was created with, whatever db.query.default_language says since (docs/deployment.md, Neo4j).
CYPHER_LANGUAGE = 'CYPHER 25'


class WrongCypherLanguage(Exception):
    pass


class Neo4jAsyncDriver(AbstractAsyncDriver):
    def __init__(self):
        self.driver: AsyncDriver = AsyncGraphDatabase.driver(
            get_bolt_url(),
            auth=get_graphdb_auth(),
            database=DATABASE_NAME,
            connection_timeout=5,
            connection_acquisition_timeout=5,
            max_transaction_retry_time=5,
            notifications_disabled_classifications=[
                NotificationClassification.UNRECOGNIZED,
            ],
        )

    def session(self):
        return self.driver.session()

    async def close(self):
        await self.driver.close()

    async def cypher_language(self) -> str | None:
        """The language the database runs queries in when they name none, e.g. 'CYPHER 25'"""
        records, _, _ = await self.driver.execute_query(
            "SHOW DATABASES YIELD name, defaultLanguage WHERE name = $name RETURN defaultLanguage",
            {'name': DATABASE_NAME}, database_='system'
        )
        return records[0]['defaultLanguage'] if records else None

    async def check_cypher_language(self) -> None:
        """Refuse a database running another Cypher than the queries are written in"""
        language = await self.cypher_language()
        if language != CYPHER_LANGUAGE:
            raise WrongCypherLanguage(
                f"The database {DATABASE_NAME} runs {language or 'an unknown Cypher'}, but BreedGraph's queries are "
                f"{CYPHER_LANGUAGE}. As Neo4j's admin: ALTER DATABASE {DATABASE_NAME} SET DEFAULT LANGUAGE "
                f"{CYPHER_LANGUAGE} (docs/upgrading.md)"
            )

    async def set_cypher_language(self) -> None:
        """Make the database run the queries' Cypher, as Neo4j's admin"""
        await self.driver.execute_query(
            f"ALTER DATABASE $name SET DEFAULT LANGUAGE {CYPHER_LANGUAGE}", {'name': DATABASE_NAME}, database_='system'
        )
