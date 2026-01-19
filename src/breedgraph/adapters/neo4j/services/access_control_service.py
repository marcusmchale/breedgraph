from typing import Dict, Set, List

from neo4j import AsyncTransaction, AsyncResult

from src.breedgraph.adapters.neo4j.cypher import queries
from src.breedgraph.adapters.neo4j.cypher.query_builders import controls
from src.breedgraph.domain.model.controls import ReadRelease, Controller, Control, ControlAuditEntry, ControlledModelLabel
from src.breedgraph.domain.model.organisations import Access
from src.breedgraph.domain.model.time_descriptors import WriteStamp, deserialize_time
from src.breedgraph.service_layer.application.access_control import AbstractAccessControlService


class Neo4jAccessControlService(AbstractAccessControlService):

    def __init__(
            self,
            tx: AsyncTransaction
    ):
        super().__init__()
        self.tx = tx

    async def _set_controls(
            self,
            label: ControlledModelLabel,
            model_ids: Set[int]|List[int],
            team_ids: Set[int]|List[int],
            user_id: int,
            release: ReadRelease
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
            model_ids: Set[int]|List[int],
            user_id: int
    ) -> None:
        if not model_ids:
            return

        await self.tx.run(
            controls.record_writes(label=label),
            entity_ids=model_ids if isinstance(model_ids, list) else list(model_ids),
            user_id=user_id,
        )

    async def _get_controllers(self, label: ControlledModelLabel, model_ids: Set[int]|List[int]) -> Dict[int, Controller]:
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
                    team_id=control['team'],
                    release=ReadRelease(control['releases'][-1]),
                    time=deserialize_time(control['times'][-1]),
                    audit=[
                        ControlAuditEntry(
                            user_id = user_id,
                            release = ReadRelease(control['releases'][i]),
                            time = deserialize_time(control['times'][i])
                        ) for i, user_id in enumerate(control['users'])
                    ]
                )
                for control in record['controls']
            }
            writes = [
                WriteStamp(user=writes['user'], time=writes['time'])
                for writes in record['writes']
            ]
            controllers[entity_id] = Controller(controls=control_map, writes=writes)
        return controllers

    async def remove_controls(self, label: ControlledModelLabel, model_ids: Set[int]|List[int], team_ids: Set[int]|List[int]) -> None:
        if not model_ids:
            return

        await self.tx.run(
            controls.remove_controls(label=label),
            entity_ids=model_ids,
            team_ids=team_ids
        )

    async def get_access_teams(self, user_id: int = None) -> Dict[Access, Set[int]]:
        """Get access teams for a user"""
        if user_id is None:
            return {a: set() for a in Access}

        result: AsyncResult = await self.tx.run(queries['controls']['get_access_teams'], user_id=user_id)
        record = await result.single()
        if record is None:
            raise ValueError("User not found")

        access_teams = {Access(key): set(value) for key, value in record.get('access_teams').items()}
        return access_teams
