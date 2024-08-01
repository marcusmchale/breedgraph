import logging

from abc import ABC, abstractmethod
from neo4j import AsyncTransaction, AsyncResult, Record
from neo4j.exceptions import ConstraintError

from src.breedgraph.domain.model.regions import (
    Region, LocationInput, LocationStored, GeoCoordinate
)
from src.breedgraph.adapters.neo4j.cypher import queries, controls
from src.breedgraph.adapters.repositories.trackable_wrappers import Tracked, TrackedList, TrackedDict

from src.breedgraph.adapters.repositories.controlled import Neo4jControlledRepository
from src.breedgraph.domain.model.controls import Controller, ReadRelease, ControlledAggregate, Control
from src.breedgraph.domain.model.accounts import AccountStored

from src.breedgraph.custom_exceptions import ProtectedNodeError, IllegalOperationError, UnauthorisedOperationError

from typing import Set, AsyncGenerator, Tuple, List

logger = logging.getLogger(__name__)

class Neo4jRegionsRepository(Neo4jControlledRepository):

    async def _create_controlled(self, location: LocationInput) -> Region:
        if location.parent:
            raise ValueError("Root of region must have no parent")

        stored_location = await self._create_location(location)
        return Region(root_id=stored_location.id, nodes={stored_location.id: stored_location})

    async def _create_location(self, location: LocationInput) -> LocationStored:
        logger.debug(f"Create location: {location}")
        params = location.model_dump()
        params['writer'] = self.account.user.id
        result: AsyncResult = await self.tx.run(
            queries['regions']['create_location'],
            params
        )
        record: Record = await result.single()
        return LocationStored(**record['location'])

    async def _get_controlled(self, member_id: int = None) -> Region | None:
        if member_id is None:
            raise ValueError(f"Get region requires location_id")

        result: AsyncResult = await self.tx.run(
            queries['regions']['get_region'],
            location=member_id
        )
        record = await result.single()
        if record:
            locations = [LocationStored(**l) for l in record['locations']]
            region = Region.from_lists(locations)
            return region
        else:
            return None

    async def _get_all_controlled(self) -> AsyncGenerator[Region, None]:
        result: AsyncResult = await self.tx.run(queries['regions']['get_regions'])
        async for record in result:
            locations = [LocationStored(**l) for l in record['locations']]
            yield Region.from_lists(locations)

    async def _remove_controlled(self, region: Region) -> None:
        for location in region.nodes.values():
            if not location.can_admin(self.account):
                raise UnauthorisedOperationError("Region can only be removed by an admin for all its locations")
        try:
            await self._remove_locations(locations=[location for location in region.nodes.values() if location.id > 0])

        except ConstraintError:
            raise ProtectedNodeError("A location in this region has relationships that cannot be removed")

    async def _remove_locations(self, locations: List[LocationStored]) -> None:
        logger.debug(f"Remove locations: {locations}")
        await self.tx.run(
            queries['regions']['remove_locations'],
            locations = [location.id for location in locations]
        )

    async def _update_members(self, members: TrackedDict[int, Tracked|LocationInput|LocationStored]):
        for location_id in members.added:
            location_id: int
            location = members[location_id]
            if location_id < 0:
                stored_location = await self._create_location(location)
                members.silent_set(stored_location.id, stored_location)
                members.silent_remove(location_id)
                if location.parent:
                    members[stored_location.parent].children.remove(location_id)
                    members[stored_location.parent].children.append(stored_location.id)

            else:
                # todo this would be needed to support incorporating a location from another region
                raise NotImplementedError

        for location_id in members.changed:
            location_id: int
            location = members[location_id]
            await self._update_location(location)

        await self._remove_locations(locations=[members[location_id] for location_id in members.removed.keys()])
        for location in members.removed.values():
            if location.parent:
                members[location.parent].children.remove(location.id)


    async def _update_location(self, location: LocationStored) -> LocationStored:
        logger.debug(f"Update location: {location}")
        params = location.model_dump()
        params['writer'] = self.account.user.id
        result: AsyncResult = await self.tx.run(
            queries['regions']['set_location'],
            params
        )
        record: Record = await result.single()
        return LocationStored(**record['location'])

    async def _update_controlled(self, region: Tracked|Region):
        await self._update_members(region.nodes)

    async def _update_control(self, entity_id: int, control: Control):
        await self.tx.run(
            controls.set_control(label='Location', plural='Locations'),
            team_id=control.team,
            release=control.release,
            entity_id=entity_id
        )

    async def _create_control(self, entity_id: int, control: Control):
        await self.tx.run(
            controls.create_control(label='Location', plural='Locations'),
            team_id=control.team,
            release=control.release,
            entity_id=entity_id
        )

    async def _remove_control(self, entity_id: int, control: Control):
        await self.tx.run(
            controls.remove_control(label='Location', plural='Locations '),
            team_id=control.team,
            entity_id=entity_id
        )