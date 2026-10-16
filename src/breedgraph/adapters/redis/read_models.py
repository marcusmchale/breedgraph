"""
Read models in Redis, each built whole from Neo4j and swapped in atomically.

A read model owns a set of hash keys. A refresh builds each into a temporary key and renames it over the old one
(or deletes the old one when it is empty), so readers never see a partial read model and stale entries go.
"""
import csv
import json
from pathlib import Path
from typing import Awaitable, Callable, Self
from uuid import uuid4

import redis.asyncio as redis
from neo4j import AsyncResult

from breedgraph.config import COUNTRY_CODES_PATH, get_redis_host_and_port
from breedgraph.domain.model.controls import ReadRelease
from breedgraph.domain.model.ontology import OntologyEntryLabel
from breedgraph.service_layer.application.ontology_seed import COUNTRY
from breedgraph.domain.model.location_trees import LocationInput, LocationOutput
from breedgraph.adapters.neo4j.driver import Neo4jAsyncDriver
from breedgraph.adapters.neo4j.services import Neo4jOntologyPersistenceService
from breedgraph.adapters.neo4j.cypher.query_builders import location_trees as location_tree_queries
from breedgraph.service_layer.infrastructure.read_models import AbstractReadModels

import logging
logger = logging.getLogger(__name__)

COUNTRY_KEY = "country"

# hash key -> field -> JSON value
ReadModelContent = dict[str, dict[str, str]]


class RedisReadModels(AbstractReadModels):
    names = ('countries', 'ontology')

    def __init__(self, connection: redis.Redis, driver: Neo4jAsyncDriver, owns_connection: bool = False):
        self.connection = connection
        self.driver = driver
        self.owns_connection = owns_connection
        self.builders: dict[str, Callable[[], Awaitable[ReadModelContent]]] = {
            'countries': self._build_countries,
            'ontology': self._build_ontology,
        }
        # the keys each read model owns, also when it has no content
        self.keys: dict[str, list[str]] = {
            'countries': [COUNTRY_KEY],
            'ontology': [label.value for label in OntologyEntryLabel],
        }

    @classmethod
    async def create(cls, driver: Neo4jAsyncDriver, connection: redis.Redis | None = None, db: int = 0) -> Self:
        if connection is not None:
            return cls(connection, driver)
        host, port = get_redis_host_and_port()
        return cls(await redis.Redis(host=host, port=port, db=db), driver, owns_connection=True)

    async def close(self) -> None:
        if self.owns_connection:
            await self.connection.aclose()

    async def _refresh(self, name: str) -> None:
        content = await self.builders[name]()
        for key in self.keys[name]:
            await self._replace(key, content.get(key, {}))
        logger.info(f"Refreshed the {name} read model")

    async def _replace(self, key: str, fields: dict[str, str]) -> None:
        if not fields:
            await self.connection.delete(key)
            return
        building = f"{key}:refresh:{uuid4().hex}"
        await self.connection.hset(building, mapping=fields)
        await self.connection.rename(building, key)

    async def _build_countries(self) -> ReadModelContent:
        """
        Countries by ISO 3166-1 alpha-3 code: the stored ones (with an id), then the others of the country codes file,
        which may be created.
        """
        countries: dict[str, str] = {}
        async with self.driver.session() as session:
            async with await session.begin_transaction() as tx:
                ontology_service = Neo4jOntologyPersistenceService(tx=tx)
                country_type_id = await ontology_service.get_entry_id_by_seed_key(COUNTRY)
                if country_type_id is None:
                    raise ValueError("The Country location type is missing: it is seeded by scripts/setup_initial_data.py")

                result: AsyncResult = await tx.run(
                    location_tree_queries.read_locations_by_type(),
                    location_type=country_type_id,
                    read_teams=[],
                    minimum_release=ReadRelease.PUBLIC
                )
                async for record in result:
                    country = LocationOutput(**record['location'])
                    countries[country.code] = json.dumps(country.model_dump())

        # e.g. https://unstats.un.org/unsd/methodology/m49/overview/
        country_codes_path = Path(COUNTRY_CODES_PATH)
        if country_codes_path.is_file():
            with open(country_codes_path) as country_codes_csv:
                for row in csv.DictReader(country_codes_csv, delimiter=";"):
                    country = LocationInput(name=row['Country or Area'], code=row['ISO-alpha3 Code'], type=country_type_id)
                    countries.setdefault(country.code, json.dumps(country.model_dump()))
        else:
            logger.warning("Couldn't find country codes to preload read model")
        return {COUNTRY_KEY: countries}

    async def _build_ontology(self) -> ReadModelContent:
        """Ontology entries by name, in one hash per label"""
        content: ReadModelContent = {}
        async with self.driver.session() as session:
            async with await session.begin_transaction() as tx:
                ontology_service = Neo4jOntologyPersistenceService(tx=tx)
                async for entry in ontology_service.get_entries():
                    content.setdefault(entry.label, {})[entry.name] = json.dumps(entry.model_dump())
        return content
