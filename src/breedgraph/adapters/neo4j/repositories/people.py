import logging
import re

from breedgraph.adapters.neo4j.cypher import queries
from breedgraph.custom_exceptions import ProtectedNodeError

from breedgraph.service_layer.tracking import TrackableProtocol
from breedgraph.service_layer.repositories.controlled import ControlledQueryResult
from breedgraph.adapters.neo4j.repositories.controlled import Neo4jControlledRepository

from typing import AsyncGenerator, List

from breedgraph.domain.model.people import PersonInput, PersonStored, LawfulBasis
from breedgraph.domain.model.controls import DiscoveryMatch, Controller, Access, ControlledModelLabel
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
            name: str|None = None,
            user_id: int|None = None
    ) -> ControlledQueryResult[PersonStored]|None:
        if user_id is not None:
            result = await self.tx.run(queries['people']['get_person_by_user'], user_id=user_id)
            record = await result.single()
            if record is None:
                return None
            return ControlledQueryResult(aggregate=self.record_to_person(record['person']))
        elif person_id is not None:
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

    async def _get_all_controlled(
            self,
            name: str|None = None,
            person_ids: List[int]|None = None
    ) -> AsyncGenerator[ControlledQueryResult[PersonStored], None]:
        if person_ids is not None:
            # Lookup by ID: registered users without read access get the ID only, see PersonStored.redacted
            result = await self.tx.run(queries['people']['get_people_by_ids'], person_ids=list(person_ids))
            async for record in result:
                yield ControlledQueryResult(self.record_to_person(record['person']))
        elif name is None:
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
        changed = set(person.changed)
        if changed and changed <= {'claims'}:
            # Requests to be linked are authorised by the domain model and handlers
            return True
        is_admin = controller.has_access(Access.ADMIN, access_teams=self.access_teams[Access.ADMIN])
        if is_admin and changed <= {'user', 'claims'}:
            # Approving a request, or unlinking
            return True
        return person.erased and is_admin

    async def get_linked_user(self, person_id: int) -> int | None:
        """The account linked to a Person, for sending messages without revealing it"""
        return await self._linked_user(person_id)

    async def _linked_user(self, person_id: int) -> int | None:
        result = await self.tx.run(queries['people']['get_person'], person_id=person_id)
        record = await result.single()
        return record['person']['user'] if record else None

    async def _remove_controlled(self, person: PersonStored):
        raise ProtectedNodeError(person.protected)

    async def _update_controlled(self, person: PersonStored | TrackableProtocol):
        """
        Only changed attributes are written, so changes stored from the id-only form,
        e.g. a request to be linked, do not overwrite the rest of the record.
        """
        changed = set(person.changed)
        if not changed:
            return
        props = {}
        for attr in ('name', 'orcid', 'erased_at'):
            if attr in changed:
                props[attr] = getattr(person, attr)
        if 'basis' in changed:
            props['basis'] = person.basis.value
        await self.tx.run(
            queries['people']['set_person'],
            id=person.id,
            props=props,
            teams=list(person.teams) if 'teams' in changed else None,
            claims=list(person.claims) if 'claims' in changed else None,
            set_user='user' in changed,
            user=person.user
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
            claims=list(record.get('claims') or []),
            recorded_by=record.get('recorded_by'),
            recorded_at=deserialize_time(record.get('recorded_at')),
            erased_at=deserialize_time(record.get('erased_at'))
        )

    async def get_claim_requests(self, team_ids) -> list[dict]:
        """Pending requests to be linked to Persons controlled by the given teams"""
        result = await self.tx.run(queries['people']['get_claim_requests'], team_ids=list(team_ids))
        return [
            {**record.data(), 'time': deserialize_time(record['time'])}
            async for record in result
        ]

    async def get_claims_by_user(self, user_id: int) -> list[dict]:
        """The user's pending requests to be linked to Persons"""
        result = await self.tx.run(queries['people']['get_claims_by_user'], user_id=user_id)
        return [
            {'person_id': record['person_id'], 'time': deserialize_time(record['time'])}
            async for record in result
        ]

    async def get_contact_status(self, person_ids) -> dict[int, dict]:
        """Whether Persons exist, are linked to an account, and are erased. Reveals no personal data."""
        result = await self.tx.run(queries['people']['get_contact_status'], person_ids=list(person_ids))
        return {record['person_id']: record.data() async for record in result}

    async def get_contact_entities(self, person_id: int) -> list[tuple[ControlledModelLabel, int]]:
        """Programs and Trials listing the Person as a contact"""
        result = await self.tx.run(queries['people']['get_contact_entities'], person_id=person_id)
        return [(ControlledModelLabel(record['label']), record['id']) async for record in result]

    async def remove_contact(self, person_id: int, label: ControlledModelLabel, entity_id: int) -> bool:
        """Remove the Person as a contact of a Program or Trial. The caller authorises the change."""
        result = await self.tx.run(
            queries['people']['remove_contact'], person_id=person_id, label=label.value, entity_id=entity_id
        )
        record = await result.single()
        return bool(record and record['removed'])
