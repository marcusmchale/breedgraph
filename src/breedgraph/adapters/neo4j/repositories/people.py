import logging

from src.breedgraph.adapters.neo4j.cypher import queries
from src.breedgraph.custom_exceptions import IllegalOperationError

from src.breedgraph.service_layer.tracking import TrackableProtocol
from src.breedgraph.service_layer.repositories.controlled import ControlledQueryResult
from src.breedgraph.adapters.neo4j.repositories.controlled import Neo4jControlledRepository

from typing import AsyncGenerator

from src.breedgraph.domain.model.people import PersonInput, PersonStored
from src.breedgraph.domain.model.controls import DiscoveryMatch

logger = logging.getLogger(__name__)

class Neo4jPeopleRepository(Neo4jControlledRepository[PersonInput, PersonStored]):

    async def _create_controlled(self, person: PersonInput) -> PersonStored:
        params = person.model_dump()
        result = await self.tx.run(queries['people']['create_person'], params)
        record = await result.single()
        return PersonStored(**record['person'])

    async def _get_controlled(
            self,
            person_id: int|None = None,
            name: str|None = None
    ) -> ControlledQueryResult[PersonStored]|None:
        if person_id is not None:
            result = await self.tx.run(
                queries['people']['get_person'],
                person_id=person_id
            )
            record = await result.single(strict=True)
            return ControlledQueryResult(aggregate=PersonStored(**record['person']))
        elif name is not None:
            try:
                return await anext(self._get_all_controlled(name=name))
            except StopAsyncIteration:
                return None
        elif name is None and person_id is None:
            raise IllegalOperationError("Get person requires name or person_id")
        else:
            return None

    async def _get_all_controlled(self, name: str|None = None) -> AsyncGenerator[ControlledQueryResult[PersonStored], None]:
        if name is None:
            result = await self.tx.run(queries['people']['get_people'])
            async for record in result:
                yield ControlledQueryResult(PersonStored(**record['person']))
        else:
            result = await self.tx.run(
                queries['people']['get_people_by_name'],
                name_regex=f"(?i)^{name}$"
            )
            async for record in result:
                person=PersonStored(**record['person'])
                yield ControlledQueryResult(
                    aggregate=person,
                    matches=(DiscoveryMatch(label=PersonStored.label, model_id=person.id, key="name"),)
                )

    async def _remove_controlled(self, person: PersonStored):
        await self.tx.run(queries['people']['remove_person'], person_id=person.id)

    async def _update_controlled(self, aggregate: PersonStored | TrackableProtocol):
        if aggregate.changed:
            await self._update_person(aggregate)

    async def _update_person(self, person: PersonStored):
        params = person.model_dump()
        await self.tx.run(queries['people']['set_person'], **params)

