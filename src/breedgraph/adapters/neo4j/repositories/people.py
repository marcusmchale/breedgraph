import logging
import re

from breedgraph.adapters.neo4j.cypher import queries
from breedgraph.custom_exceptions import ProtectedNodeError

from breedgraph.service_layer.tracking import TrackableProtocol
from breedgraph.service_layer.repositories.controlled import ControlledQueryResult
from breedgraph.adapters.neo4j.repositories.controlled import Neo4jControlledRepository

from typing import AsyncGenerator

from breedgraph.domain.model.people import PersonInput, PersonStored, LawfulBasis
from breedgraph.domain.model.controls import DiscoveryMatch, Controller, Access
from breedgraph.domain.model.time_descriptors import deserialize_time

logger = logging.getLogger(__name__)

class Neo4jPeopleRepository(Neo4jControlledRepository[PersonInput, PersonStored]):

    async def _create_controlled(self, person: PersonInput) -> PersonStored:
        result = await self.tx.run(
            queries['people']['create_person'],
            name=person.name,
            teams=list(person.teams or []),
            basis=person.basis.value,
            informed_attestation=person.informed_attestation,
            recorded_by=self.user_id
        )
        record = await result.single()
        return self.record_to_person(record['person'])

    async def _get_controlled(
            self,
            person_id: int|None = None,
            name: str|None = None
    ) -> ControlledQueryResult[PersonStored]|None:
        if person_id is not None:
            result = await self.tx.run(queries['people']['get_person'], person_id=person_id)
            record = await result.single()
            if record is None:
                return None
            return ControlledQueryResult(aggregate=self.record_to_person(record['person']))
        elif name is not None:
            try:
                return await anext(self._get_all_controlled(name=name))
            except StopAsyncIteration:
                return None
        else:
            try:
                return await anext(self._get_all_controlled())
            except StopAsyncIteration:
                return None

    async def _get_all_controlled(self, name: str|None = None) -> AsyncGenerator[ControlledQueryResult[PersonStored], None]:
        if name is None:
            result = await self.tx.run(queries['people']['get_people'])
            async for record in result:
                yield ControlledQueryResult(self.record_to_person(record['person']))
        else:
            result = await self.tx.run(
                queries['people']['get_people_by_name'],
                name_regex=f"(?i)^{re.escape(name)}$"
            )
            async for record in result:
                person = self.record_to_person(record['person'])
                yield ControlledQueryResult(
                    aggregate=person,
                    matches=(DiscoveryMatch(label=PersonStored.label, model_id=person.id, key="name"),)
                )

    async def _can_change(self, person: PersonStored, controller: Controller) -> bool:
        """
        Besides curators, the linked user can change their own record,
        and admins of the controlling teams can store an erasure.
        Which changes are allowed is decided by the domain model and handlers.
        The stored link is checked, as erasing removes the link from the model.
        """
        if await super()._can_change(person, controller):
            return True
        if self.user_id is not None and await self._linked_user(person.id) == self.user_id:
            return True
        return person.erased and controller.has_access(Access.ADMIN, access_teams=self.access_teams[Access.ADMIN])

    async def   _linked_user(self, person_id: int) -> int | None:
        result = await self.tx.run(queries['people']['get_person'], person_id=person_id)
        record = await result.single()
        return record['person']['user'] if record else None

    async def _remove_controlled(self, person: PersonStored):
        raise ProtectedNodeError(person.protected)

    async def _update_controlled(self, person: PersonStored | TrackableProtocol):
        if not person.changed:
            return
        await self.tx.run(
            queries['people']['set_person'],
            id=person.id,
            name=person.name,
            teams=list(person.teams),
            basis=person.basis.value,
            orcid=person.orcid,
            user=person.user,
            erased_at=person.erased_at
        )

    @staticmethod
    def record_to_person(record: dict) -> PersonStored:
        return PersonStored(
            id=record['id'],
            name=record.get('name'),
            teams=list(record.get('teams') or []),
            basis=LawfulBasis(record['basis']),
            informed_attestation=record.get('informed_attestation', False),
            orcid=record.get('orcid'),
            user=record.get('user'),
            recorded_by=record.get('recorded_by'),
            recorded_at=deserialize_time(record.get('recorded_at')),
            erased_at=deserialize_time(record.get('erased_at'))
        )
