import logging

from src.breedgraph.adapters.neo4j.cypher import queries
from src.breedgraph.service_layer.tracking import TrackableProtocol
from src.breedgraph.adapters.neo4j.repositories.controlled import Neo4jControlledRepository

from typing import AsyncGenerator

from src.breedgraph.domain.model.people import PersonInput, PersonStored

logger = logging.getLogger(__name__)

class Neo4jPeopleRepository(Neo4jControlledRepository[PersonInput, PersonStored]):

    async def _create_controlled(self, person: PersonInput) -> PersonStored:
        params = person.model_dump()
        result = await self.tx.run(queries['people']['create_person'], params)
        record = await result.single()
        return PersonStored(**record['person'])

    async def _get_controlled(
            self,
            person_id: int = None
    ) -> PersonStored|None:

        if person_id is None:
            raise TypeError(f"person_id is required")

        result = await self.tx.run(
            queries['people']['get_person'],
            person_id=person_id
        )
        record = await result.single()
        if record:
            return PersonStored(**record['person'])
        else:
            return None

    async def _get_all_controlled(self) -> AsyncGenerator[PersonStored, None]:
        result = await self.tx.run(queries['people']['get_people'])
        async for record in result:
            yield PersonStored(**record['person'])

    async def _remove_controlled(self, person: PersonStored):
        await self.tx.run(queries['people']['remove_person'], person_id=person.id)

    async def _update_controlled(self, aggregate: PersonStored | TrackableProtocol):
        if aggregate.changed:
            await self._update_person(aggregate)

    async def _update_person(self, person: PersonStored):
        params = person.model_dump()
        await self.tx.run(queries['people']['set_person'], **params)

