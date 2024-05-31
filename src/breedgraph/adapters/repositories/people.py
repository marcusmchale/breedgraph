import logging

from neo4j import AsyncTransaction, Record

from src.breedgraph.adapters.neo4j.cypher import queries

from src.breedgraph.adapters.repositories.trackable_wrappers import Tracked
from src.breedgraph.adapters.repositories.base import ControlledRepository

from typing import AsyncGenerator

from src.breedgraph.domain.model.people import Person, PersonStored, PersonRecord
from src.breedgraph.domain.model.base import RecordController, Release

from typing import List

logger = logging.getLogger(__name__)

class Neo4jPeopleRepository(ControlledRepository):

    def __init__(self, tx: AsyncTransaction, user:int, release: Release = Release.REGISTERED):
        super().__init__(user)
        self.tx = tx
        self.release = release

    async def _create(
            self,
            person: Person
    ) -> PersonRecord:
        result = await self.tx.run(
            queries['people']['create_person'],
            {**dict(person), 'writer': self.user, 'release': self.release}
        )
        record = await result.single()
        import pdb; pdb.set_trace()
        return PersonRecord(
            person=PersonStored(**record['person']),
            controller=RecordController(**record['controller'])
        )

    async def _get(
            self,
            person_id: int = None
    ) -> PersonRecord|None:
        if person_id is None:
            raise TypeError(f"person_id is required")

        result = await self.tx.run(
            queries['people']['get_person'],
            person_id=person_id
        )
        record = await result.single()
        if record:
            controller = RecordController(**record['controller'])
            if controller.user_can_read(user_id = self.user):
                person = PersonStored(**record['person'])
                return PersonRecord(person=person, controller=controller)

    async def _get_all(self) -> AsyncGenerator[PersonRecord, None]:
        result = await self.tx.run(queries['people']['get_people'])
        async for record in result:
            controller = RecordController(**record['controller'])
            if controller.user_can_read(self.user):
                yield PersonRecord(person=PersonStored(**record['person']), controller=controller)

    async def _update(self, person: PersonRecord|Tracked):
        if not person.changed:
            return
        elif person.controller.user_can_write(self.user):
            await self.tx.run(
                queries['people']['set_person'],
                {**dict(person), 'writer':self.user}
            )

    async def _remove(self, person) -> None:

        await self.tx.run(queries['people']['remove_person'], person_id=person.id)