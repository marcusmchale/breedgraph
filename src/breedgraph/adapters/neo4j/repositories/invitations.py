from typing import AsyncGenerator

from neo4j import AsyncTransaction

from breedgraph.adapters.neo4j.cypher import queries
from breedgraph.domain.model.invitations import InvitationInput, InvitationStored, TeamInvitation
from breedgraph.domain.model.time_descriptors import deserialize_time
from breedgraph.service_layer.repositories.base import BaseRepository
from breedgraph.service_layer.tracking import TrackableProtocol

import logging
logger = logging.getLogger(__name__)


class Neo4jInvitationsRepository(BaseRepository[InvitationInput, InvitationStored]):
    """
    Access to invitations is checked by the handlers using them:
    inviters manage their own invitations, and invited users present a signed token.
    """

    def __init__(self, tx: AsyncTransaction, expiry_days: int):
        super().__init__()
        self.tx = tx
        self.expiry_days = expiry_days

    async def _create(self, invitation: InvitationInput) -> InvitationStored:
        result = await self.tx.run(
            queries['invitations']['create_invitation'],
            email=invitation.email,
            email_lower=invitation.email.casefold(),
            invited_by=invitation.invited_by,
            teams=[{'team_id': team.team_id, 'access': team.access.value} for team in invitation.teams],
            person_id=invitation.person_id,
            expiry_days=self.expiry_days
        )
        record = await result.single()
        if record is None:
            raise ValueError(f"Inviting user {invitation.invited_by} not found")
        return self.record_to_invitation(record['invitation'])

    async def _get(self, invitation_id: int) -> InvitationStored | None:
        result = await self.tx.run(queries['invitations']['get_invitation'], invitation_id=invitation_id)
        record = await result.single()
        return self.record_to_invitation(record['invitation']) if record else None

    async def _get_all(
            self,
            invited_by: int | None = None,
            email: str | None = None
    ) -> AsyncGenerator[InvitationStored, None]:
        result = await self.tx.run(
            queries['invitations']['get_invitations'],
            invited_by=invited_by,
            email_lower=email.strip().casefold() if email else None
        )
        async for record in result:
            yield self.record_to_invitation(record['invitation'])

    async def _remove(self, invitation: InvitationStored | TrackableProtocol) -> None:
        await self.tx.run(queries['invitations']['delete_invitation'], invitation_id=invitation.id)

    async def _update(self, invitation: InvitationStored | TrackableProtocol) -> None:
        if 'expires_at' in invitation.changed:
            await self.tx.run(
                queries['invitations']['set_invitation'],
                invitation_id=invitation.id,
                expires_at=invitation.expires_at
            )

    async def remove_expired(self) -> int:
        result = await self.tx.run(queries['invitations']['delete_expired_invitations'])
        record = await result.single()
        return record['deleted']

    @staticmethod
    def record_to_invitation(record: dict) -> InvitationStored:
        return InvitationStored(
            id=record['id'],
            email=record['email'],
            invited_by=record['invited_by'],
            teams=[TeamInvitation(team_id=team['team_id'], access=team['access']) for team in record['teams']],
            person_id=record['person_id'],
            created_at=deserialize_time(record['created_at']),
            expires_at=deserialize_time(record['expires_at'])
        )
