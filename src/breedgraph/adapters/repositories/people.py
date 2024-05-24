import logging

from neo4j import AsyncTransaction, Record

from src.breedgraph.adapters.neo4j.cypher import queries

from src.breedgraph.adapters.repositories.trackable_wrappers import Tracked
from src.breedgraph.adapters.repositories.base import BaseRepository

from typing import AsyncGenerator

from src.breedgraph.domain.model.people import Person, PersonStored

logger = logging.getLogger(__name__)

class Neo4jPeopleRepository(BaseRepository):

    def __init__(self, tx: AsyncTransaction):
        super().__init__()
        self.tx = tx

    async def _create(self, person: Person) -> PersonStored:
        result = await self.tx.run(
            queries['people']['create_person']
            **person
        )
        record = await result.single()
        return PersonStored(**record)

    @staticmethod
    def record_to_entry(record: Record) -> PersonStored:
        return PersonStored(**record)

    async def _get(self, person_id: int = None) -> PersonStored|None:
        if person_id is not None:
            result = await self.tx.run(queries['people']['get_person'], person_id=person_id)

        else:
            raise TypeError(f"Get person requires person_id")
        record = await result.single()
        return PersonStored(**record)

    async def _get_all(self) -> AsyncGenerator[PersonStored, None]:
        result = await self.tx.run(queries['people']['get_people'])
        async for record in result:
            yield PersonStored(**record)

    async def _update(self, person: Person|Tracked):
        if not person.changed:
            return
        else:
            await self.tx.run(queries['people']['set_person'], **person)

    async def _remove(self, person) -> None:
        await self.tx.run(queries['people']['remove_person'], person_id=person.id)