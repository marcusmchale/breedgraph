from neo4j import AsyncSession

from breedgraph.adapters.neo4j.cypher.query_builders import controls as control_queries
from breedgraph.domain.model.controls import Controller, Control, ControlledModelLabel, ReadRelease
from breedgraph.domain.model.time_descriptors import WriteStamp, deserialize_time
from breedgraph.domain.model.unit_graphs import UnitOutput
from breedgraph.service_layer.queries.views.accounts import AbstractAccountsView
from breedgraph.service_layer.queries.views.controls import (
    AbstractControlsView, ControlledCount, ControlledItem, ControlledItems, ControlledUnitNode
)

from typing import Dict, List


class Neo4jControlsView(AbstractControlsView):
    """The read check and placeholders are in the Cypher (see query_builders.controls)"""

    def __init__(self, session: AsyncSession, user_id: int | None, read_teams: List[int], accounts: AbstractAccountsView):
        self.session = session
        self.user_id = user_id
        self.read_teams = read_teams
        self.accounts = accounts

    @property
    def minimum_release(self) -> int:
        return int(ReadRelease.PUBLIC if self.user_id is None else ReadRelease.REGISTERED)

    async def _get_admin_teams(self) -> List[int]:
        return await self.accounts.get_admin_teams() if self.user_id is not None else []

    async def _get_controlled_counts(self, team_ids: List[int]) -> List[ControlledCount]:
        result = await self.session.run(control_queries.read_controlled_counts(), team_ids=team_ids)
        return [
            ControlledCount(
                team_id=record['team_id'],
                label=ControlledModelLabel[record['label']],
                release=ReadRelease(record['release']),
                count=record['count']
            )
            async for record in result
        ]

    async def _get_controlled_entities(
            self, team_id: int, label: ControlledModelLabel, release: ReadRelease | None, offset: int, limit: int
    ) -> ControlledItems:
        result = await self.session.run(
            control_queries.read_controlled_entities(label),
            team_id=team_id,
            release=None if release is None else int(release),
            offset=offset,
            limit=limit,
            read_teams=self.read_teams,
            minimum_release=self.minimum_release
        )
        record = await result.single()
        if record is None:
            return ControlledItems(total=0, items=[])
        return ControlledItems(
            total=record['total'],
            items=[
                ControlledItem(
                    label=label,
                    id=item['id'],
                    name=item['name'],
                    release=ReadRelease(item['release']),
                    other_team_ids=list(item['other_team_ids']),
                    context=item['context']
                )
                for item in record['items']
            ]
        )

    async def _get_entity_names(self, label: ControlledModelLabel, entity_ids: List[int]) -> Dict[int, str | None]:
        result = await self.session.run(
            control_queries.read_entity_names(label),
            ids=entity_ids,
            read_teams=self.read_teams,
            minimum_release=self.minimum_release
        )
        return {record['id']: record['name'] async for record in result}

    async def _units(self, query: str, **params) -> List[ControlledUnitNode]:
        result = await self.session.run(query, **params, read_teams=self.read_teams, minimum_release=self.minimum_release)
        return [
            ControlledUnitNode(
                unit=UnitOutput(**dict(record['unit'])),
                parent_id=record['parent_id'],
                count=record['count'],
                release=None if record['release'] is None else ReadRelease(record['release']),
                other_team_ids=list(record['other_team_ids'])
            )
            async for record in result
        ]

    async def _get_controlled_unit_roots(self, team_id: int) -> List[ControlledUnitNode]:
        return await self._units(control_queries.read_controlled_unit_roots(), team_id=team_id)

    async def _get_controlled_unit_children(self, team_id: int, parent_ids: List[int]) -> List[ControlledUnitNode]:
        return await self._units(control_queries.read_controlled_unit_children(), team_id=team_id, parent_ids=parent_ids)

    async def _get_controllers(self, label: ControlledModelLabel, entity_ids: List[int]) -> Dict[int, Controller]:
        result = await self.session.run(
            control_queries.read_controllers(label),
            entity_ids=entity_ids,
            read_teams=self.read_teams,
            minimum_release=int(ReadRelease.PUBLIC if self.user_id is None else ReadRelease.REGISTERED)
        )
        controllers = {}
        async for record in result:
            controls = {
                control['team']: Control(
                    user_id=control['user'],
                    team_id=control['team'],
                    release=ReadRelease(control['release']),
                    time=deserialize_time(control['time'])
                )
                for control in record['controls']
            }
            # in the order they were made
            writes = [
                WriteStamp(user=write['user'], time=deserialize_time(write['time']))
                for write in sorted(record['writes'], key=lambda write: write['time'])
            ]
            controllers[record['entity_id']] = Controller(controls=controls, writes=writes)
        return controllers
