from typing import Iterable, List, Set

from neo4j import AsyncTransaction, AsyncResult

from breedgraph.adapters.neo4j.cypher import queries
from breedgraph.adapters.neo4j.cypher.query_builders import controls
from breedgraph.domain.model.controls import (
    ReadRelease, Controller, Control, ControlledModelLabel, Access
)
from breedgraph.domain.model.control_transfers import (
    ControlledEntity, ControlTransferInput, ControlTransferStored, ControlTransferStatus
)
from breedgraph.domain.model.time_descriptors import WriteStamp, deserialize_time
from breedgraph.service_layer.application.access_control import AbstractAccessControlService


class Neo4jAccessControlService(AbstractAccessControlService):

    def __init__(
            self,
            tx: AsyncTransaction,
            user_id: int|None,
            access_teams: dict[Access, set[int]]
    ):
        super().__init__()
        self.tx = tx
        self.user_id = user_id
        self.access_teams = access_teams

    @classmethod
    async def create(cls, tx, user_id):
        access_teams = {a: set() for a in Access}

        if user_id is not None:
            access_teams.update(await cls._load_access_teams(tx, user_id))

        return cls(tx, user_id, access_teams)

    @classmethod
    async def _load_access_teams(cls, tx: AsyncTransaction, user_id: int | None = None) -> dict[Access, set[int]]:
        """Get access teams for a user"""
        result: AsyncResult = await tx.run(queries['controls']['get_access_teams'], user_id=user_id)
        record = await result.single()
        if record is None:
            raise ValueError("User not found")

        access_teams = {Access(key): set(value) for key, value in record.get('access_teams').items()}
        return access_teams

    async def _set_controls(
            self,
            label: ControlledModelLabel,
            model_ids: Iterable[int],
            team_ids: Iterable[int],
            release: ReadRelease,
            user_id: int
    ) -> None:
        if not model_ids:
            return

        await self.tx.run(
            controls.set_controls(label=label),
            entity_ids=model_ids if isinstance(model_ids, list) else list(model_ids),
            team_ids=team_ids if isinstance(team_ids, list) else list(team_ids),
            user_id=user_id,
            release=release.value
        )

    async def _record_writes(
            self,
            label: ControlledModelLabel,
            model_ids: Iterable[int],
            user_id: int
    ) -> None:
        if not model_ids:
            return

        await self.tx.run(
            controls.record_writes(label=label),
            entity_ids=model_ids if isinstance(model_ids, list) else list(model_ids),
            user_id=user_id,
        )

    async def _get_controllers(self, label: ControlledModelLabel, model_ids: Iterable[int]) -> dict[int, Controller]:
        if not model_ids:
            return {}

        result = await self.tx.run(
            controls.get_controllers(label=label),
            entity_ids=model_ids
        )
        controllers = {}
        async for record in result:
            entity_id = record['entity_id']
            control_map = {
                control['team']: Control(
                    user_id=control['user'],
                    team_id=control['team'],
                    release=ReadRelease(control['release']),
                    time=deserialize_time(control['time'])
                )
                for control in record['controls']
            }
            writes = [
                WriteStamp(user=writes['user'], time=writes['time'])
                for writes in record['writes']
            ]
            controllers[entity_id] = Controller(controls=control_map, writes=writes)
        return controllers

    async def _add_controls(
            self,
            label: ControlledModelLabel,
            model_ids: Iterable[int],
            team_ids: Iterable[int],
            release: ReadRelease,
            user_id: int
    ) -> None:
        if not model_ids:
            return

        await self.tx.run(
            controls.add_controls(label=label),
            entity_ids=list(model_ids),
            team_ids=list(team_ids),
            user_id=user_id,
            release=release.value
        )

    async def _end_controls(
            self,
            label: ControlledModelLabel,
            model_ids: Iterable[int],
            team_ids: Iterable[int],
            user_id: int
    ) -> None:
        if not model_ids:
            return

        await self.tx.run(
            controls.end_controls(label=label),
            entity_ids=list(model_ids),
            team_ids=list(team_ids),
            user_id=user_id
        )

    async def _get_team_and_descendants(self, team_id: int) -> Set[int]:
        result = await self.tx.run(queries['controls']['get_team_and_descendants'], team_id=team_id)
        record = await result.single()
        return set(record['team_ids']) if record else set()

    async def _create_transfer(self, transfer: ControlTransferInput) -> ControlTransferStored:
        result = await self.tx.run(
            queries['control_transfers']['create_control_transfer'],
            entity_labels=[entity.label.value for entity in transfer.entities],
            entity_ids=[entity.id for entity in transfer.entities],
            from_teams=list(transfer.from_teams),
            recipient_team=transfer.recipient_team,
            keep_from_teams=transfer.keep_from_teams,
            offered_by=transfer.offered_by
        )
        record = await result.single()
        return self.record_to_transfer(record['transfer'])

    async def _get_transfer(self, transfer_id: int) -> ControlTransferStored | None:
        result = await self.tx.run(queries['control_transfers']['get_control_transfer'], transfer_id=transfer_id)
        record = await result.single()
        return self.record_to_transfer(record['transfer']) if record else None

    async def _get_transfers(
            self,
            recipient_teams: Iterable[int] | None = None,
            from_teams: Iterable[int] | None = None,
            statuses: Iterable[ControlTransferStatus] | None = None
    ) -> List[ControlTransferStored]:
        result = await self.tx.run(
            queries['control_transfers']['get_control_transfers'],
            recipient_teams=list(recipient_teams) if recipient_teams is not None else None,
            from_teams=list(from_teams) if from_teams is not None else None,
            statuses=[status.value for status in statuses] if statuses is not None else None
        )
        return [self.record_to_transfer(record['transfer']) async for record in result]

    async def _set_transfer(self, transfer: ControlTransferStored) -> ControlTransferStored:
        result = await self.tx.run(
            queries['control_transfers']['set_control_transfer'],
            id=transfer.id,
            status=transfer.status.value,
            to_teams=list(transfer.to_teams),
            release=transfer.release.value if transfer.release is not None else None,
            accepted_by=transfer.accepted_by,
            rejected_by=transfer.rejected_by,
            cancelled_by=transfer.cancelled_by
        )
        record = await result.single()
        return self.record_to_transfer(record['transfer'])

    @staticmethod
    def record_to_transfer(record: dict) -> ControlTransferStored:
        return ControlTransferStored(
            id=record['id'],
            entities=[
                ControlledEntity(label=ControlledModelLabel(label), id=entity_id)
                for label, entity_id in zip(record['entity_labels'], record['entity_ids'])
            ],
            from_teams=list(record['from_teams']),
            recipient_team=record['recipient_team'],
            keep_from_teams=record['keep_from_teams'],
            offered_by=record['offered_by'],
            status=ControlTransferStatus(record['status']),
            to_teams=list(record.get('to_teams') or []),
            release=ReadRelease(record['release']) if record.get('release') is not None else None,
            offered_at=deserialize_time(record.get('offered_at')),
            accepted_by=record.get('accepted_by'),
            accepted_at=deserialize_time(record.get('accepted_at')),
            rejected_by=record.get('rejected_by'),
            rejected_at=deserialize_time(record.get('rejected_at')),
            cancelled_by=record.get('cancelled_by'),
            cancelled_at=deserialize_time(record.get('cancelled_at'))
        )
