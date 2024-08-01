import logging

from neo4j import AsyncTransaction, Record

from src.breedgraph.custom_exceptions import UnauthorisedOperationError

from src.breedgraph.adapters.neo4j.cypher import queries, controls

from src.breedgraph.adapters.repositories.trackable_wrappers import Tracked, TrackedList
from src.breedgraph.adapters.repositories.controlled import Neo4jControlledRepository

from typing import AsyncGenerator

from src.breedgraph.domain.model.base import Aggregate
from src.breedgraph.domain.model.people import PersonInput, PersonStored
from src.breedgraph.domain.model.controls import Controller, ReadRelease, Control
from src.breedgraph.domain.model.accounts import AccountStored

from typing import Tuple, List, Protocol

logger = logging.getLogger(__name__)


class Neo4jPeopleRepository(Neo4jControlledRepository):


    async def _create_controlled(
            self,
            person: PersonInput
    ) -> PersonStored:
        params = person.model_dump()
        params['writer'] = self.account.user.id
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
            person = PersonStored(**record['person'])
            return person
        else:
            return None

    async def _get_all_controlled(self) -> AsyncGenerator[PersonStored, None]:
        result = await self.tx.run(queries['people']['get_people'])
        async for record in result:
            yield PersonStored(**record['person'])

    async def _remove_controlled(self, person: PersonStored):
        if not person.controller.can_admin(self.account):
            raise UnauthorisedOperationError("Person can only be removed by an admin for the person record")

        await self.tx.run(queries['people']['remove_person'], person_id=person.id)

    async def _update_controlled(self, person: PersonStored|Tracked):
        if person.changed:
            if 'controller' in person.changed:
                if not person.controller.can_admin(self.account):
                    raise UnauthorisedOperationError("Only admins can change controls")

                await self._update_entity_controller(person)

            if person.changed != {'controller'}:
                if not person.controller.can_curate(self.account):
                    raise UnauthorisedOperationError("Updates can only be performed by accounts with curate control")

                await self._update_person(person)

    async def _update_person(self, person: PersonStored):
        params = person.model_dump()
        params['writer'] = self.account.user.id
        await self.tx.run(queries['people']['set_person'], params)
