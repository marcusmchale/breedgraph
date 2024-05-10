import logging

from abc import ABC, abstractmethod
from neo4j import AsyncTransaction, AsyncResult, Record
from neo4j.exceptions import ConstraintError

from src.breedgraph.domain.model.locations import (
    Country, Location, LocationStored, LocationType, LocationTypeStored, Coordinate
)
from src.breedgraph.adapters.neo4j.cypher import queries
from src.breedgraph.adapters.repositories.trackable_wrappers import Tracked, TrackedList
from src.breedgraph.custom_exceptions import ProtectedNodeError, IllegalOperationError


from typing import Set, AsyncGenerator

logger = logging.getLogger(__name__)

class BaseCountriesRepository(ABC):

    def __init__(self):
        self.seen: Set[Country] = set()

    def _track(self, country: Country):
        country.locations = TrackedList(country.locations)
        self.seen.add(country)

    async def create(self, country: Country) -> Country:
        country_stored = await self._create(country)
        self._track(country_stored)
        return country_stored

    @abstractmethod
    async def _create(self, country: Country) -> Country:
        raise NotImplementedError

    async def get(self, code: str) -> Country:
        country = await self._get(code)
        if country is not None:
            self._track(country)
        return country

    @abstractmethod
    async def _get(self, code: str) -> Country:
        raise NotImplementedError

    async def get_all(self) -> AsyncGenerator[Country, None]:
        async for country in self._get_all():
            self._track(country)
            yield country

    @abstractmethod
    def _get_all(self) -> AsyncGenerator[Country, None]:
        raise NotImplementedError

    async def remove(self, country: Country):
        if country.root.locations:
            raise ProtectedNodeError

        await self._remove(country)

    @abstractmethod
    async def _remove(self, country: Country):
        raise NotImplementedError

    async def update_seen(self):
        for country in self.seen:
            await self._update(country)
        self.seen.clear()

    @abstractmethod
    async def _update(self, country: Country):
        raise NotImplementedError


class Neo4jCountriesRepository(BaseCountriesRepository):

    def __init__(self, tx: AsyncTransaction):
        super().__init__()
        self.tx = tx

    async def _create(self, country: Country) -> Country:
        locations = [await self._create_location(location) for location in country.locations]
        country.locations = locations
        return country

    async def _get(self, location_id: int) -> Country:
        result: AsyncResult = await self.tx.run(
            queries['get_country'],
            location=location_id
        )
        record = await result.single()
        locations = [self.record_to_location(l) for l in record['locations']]
        return Country(locations=locations)

    async def _get_all(self) -> AsyncGenerator[Country, None]:
        result: AsyncResult = await self.tx.run(
            queries['get_countries']
        )
        async for record in result:
            locations = [self.record_to_location(l) for l in record['locations']]
            yield Country(locations=locations)

    async def _store_country(self, country: Country) -> None:
        # not quite the same as create, store means it exists in the read model but isn't in neo4j
        # here that is because it is loaded from a csv file to serve as precached suggestions.
        await self.tx.run(queries['store_country'], name=country.name, code=country.code)

    async def _remove_country(self, country: Country) -> None:
        try:
            await self.tx.run(queries['remove_country'], name=country.name, code=country.code)
        except ConstraintError:
            raise ProtectedNodeError("This country has existing relationships and cannot be removed")

    async def _create_location(self, location: Location):
        logger.debug(f"Create location: {location}")
        params = {
            'type': location.type,
            'code': location.code,
            'parent': location.parent,
            'name': location.name,
            'fullname': location.fullname if location.fullname is not None else location.name,
            'description': location.description,
            'address': location.address,
            'coordinates': [
                {
                    'sequence': i,  # sequence is important in constructing a polygon
                    'latitude': coordinate.latitude,
                    'longitude': coordinate.longitude,
                    'altitude': coordinate.altitude,
                    'uncertainty': coordinate.uncertainty,
                    'description': coordinate.description
                } for (i, coordinate) in enumerate(location.coordinates)
            ]
        }
        result: AsyncResult = await self.tx.run(
            queries['create_location'],
            params
        )
        record: Record = await result.single()
        return self.record_to_location(record['location'])

    async def _set_location(self, location: LocationStored):
        logger.debug(f"Set location: {location}")
        params = {
            'type': location.type,
            'name': location.name,
            'fullname': location.fullname if location.fullname is not None else location.name,
            'description': location.description,
            'address': location.address,
            'coordinates': [
                {
                    'sequence': i,  # sequence is important in constructing a polygon
                    'latitude': coordinate.latitude,
                    'longitude': coordinate.longitude,
                    'altitude': coordinate.altitude,
                    'uncertainty': coordinate.uncertainty,
                    'description': coordinate.description
                } for (i, coordinate) in enumerate(location.coordinates)
            ]
        }
        if isinstance(location.parent, int):
            params['parent'] = location.parent
            result: AsyncResult = await self.tx.run(
                queries['set_location'],
                params
            )
        else:
            params['country'] = country.code

        await self.tx.run(
            queries['set_location'],
            type=location.type,
        )




    async def _set_location_type(self, location: LocationStored):
        logger.debug(f"Set type for {location}")
        await self.tx.run(queries['set_location_type'], location=location.id, new_type=LocationTypeStored.id)

    async def _relocate(self, location: LocationStored, parent: int|str):
        logger.debug(f"Relocating {location}")
        if isinstance(parent, int):
            await self.tx.run(queries['relocate'], location=location.id, parent=parent)
        elif isinstance(parent, str):
            await self.tx.run(queries['relocate_to_country'], location=location.id, country=parent)

    async def _remove(self, country: Country):
        logger.debug(f"Removing country and all its locations: {country}")
        for l in country.locations:
            if isinstance(l, LocationStored):
                await self._remove_location(l)
        await self._remove_country(country)

    async def _remove_location(self, location: LocationStored):
        logger.debug(f"Removing location: {location}")
        await self.tx.run(
            queries['remove_location'],
            location=location.id
        )

    async def _update(self, country: Country):
        if not isinstance(country.locations, Tracked):
            raise IllegalOperationError("Country locations must be tracked for neo4j updates")

        if not country.locations.changed:
            return

        for location in country.locations:
            if location.changed or location in country.locations.added:
                if isinstance(location, LocationStored):
                    await self._set_location(location)
                else:
                    await self._create_location(location, country)

        for location in country.locations.removed:
            await self._remove_location(location)

    @staticmethod
    def record_to_location(record) -> LocationStored:
        coordinates = [
            Coordinate(
                latitude=c['latitude'],
                longitude=c['longitude'],
                altitude=c['altitude'],
                uncertainty=c['uncertainty'],
                description=c['description']
            )
            for c in record['coordinates']
        ]

        return LocationStored(
            id=record['id'],
            type=record['type'],
            name=record['name'],
            fullname=record['fullname'],
            parent=record['parent'],
            children=record['children'],
            coordinates = coordinates,
        )
