import logging

from neo4j import AsyncTransaction, Record

from src.breedgraph.custom_exceptions import UnauthorisedOperationError

from src.breedgraph.adapters.neo4j.cypher import queries

from src.breedgraph.adapters.repositories.trackable_wrappers import Tracked
from src.breedgraph.adapters.repositories.controlled import ControlledRepository

from typing import AsyncGenerator

from src.breedgraph.domain.model.base import Aggregate
from src.breedgraph.domain.model.people import Person, PersonStored
from src.breedgraph.domain.model.controls import RecordController, Release
from src.breedgraph.domain.model.accounts import AccountStored

from typing import Tuple, List

logger = logging.getLogger(__name__)

class Neo4jPeopleRepository(ControlledRepository):

    def __init__(self, tx: AsyncTransaction, account:AccountStored|None):
        super().__init__(account)
        self.tx = tx

    async def _create_controlled(
            self,
            person: Person
    ) -> PersonStored:
        result = await self.tx.run(
            queries['people']['create_person'],
            {
                **dict(person),
                'writer': self.account.user.id,
                'writes_for': self.writes_for,
                'release': Release.PRIVATE,
            }
        )
        record = await result.single()
        return PersonStored(**record['person'])

    async def _get_controlled(
            self,
            person_id: int = None
    ) -> Tuple[PersonStored, RecordController]|None:
        if person_id is None:
            raise TypeError(f"person_id is required")

        result = await self.tx.run(
            queries['people']['get_person'],
            person_id=person_id
        )
        record = await result.single()
        if record:
            return PersonStored(**record['person']), self.record_to_controller(record['controller'])
        else:
            return None

    async def _get_all_controlled(self) -> AsyncGenerator[Tuple[PersonStored, RecordController], None]:
        result = await self.tx.run(queries['people']['get_people'])
        async for record in result:
            yield PersonStored(**record['person']), self.record_to_controller(record['controller'])

    async def _get_controller(self, person: PersonStored) -> RecordController:
        result = await self.tx.run(queries['people']['get_controller'], person_id=person.id)
        record = await result.single()
        return self.record_to_controller(record)

    async def _remove_controlled(self, person: PersonStored):
        await self.tx.run(queries['people']['remove_person'], person_id=person.id)

    async def _update_controlled(self, person: PersonStored|Tracked):
        await self.tx.run(
            queries['people']['set_person'],
            {
                **dict(person),
                'writer':self.account.user.id
            })

    async def _set_release(self, person: PersonStored|Tracked, release: Release):
        await self.tx.run(
            queries['people']['set_release'],
            person_id = person.id,
            controllers = self.account.admins,
            release = release
        )

    async def _add_control(self, person: PersonStored, team: int, release: Release):
        await self.tx.run(
            queries['people']['add_control'],
            person_id = person.id,
            team_id = team,
            release = release
        )

    async def _remove_control(self, person: PersonStored, team: int):
        await self.tx.run(
            queries['people']['remove_control'],
            person_id=person.id,
            team_id=team
        )