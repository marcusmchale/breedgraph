from neo4j import AsyncSession

from breedgraph.adapters.neo4j.cypher.query_builders import controls as control_queries
from breedgraph.domain.model.controls import Controller, Control, ControlledModelLabel, ReadRelease
from breedgraph.domain.model.time_descriptors import WriteStamp, deserialize_time
from breedgraph.service_layer.queries.views.controls import AbstractControlsView

from typing import Dict, List


class Neo4jControlsView(AbstractControlsView):
    """The read check and placeholders are in the Cypher (see query_builders.controls.read_controllers)"""

    def __init__(self, session: AsyncSession, user_id: int | None, read_teams: List[int]):
        self.session = session
        self.user_id = user_id
        self.read_teams = read_teams

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
                WriteStamp(user=write['user'], time=write['time'])
                for write in sorted(record['writes'], key=lambda write: write['time'])
            ]
            controllers[record['entity_id']] = Controller(controls=controls, writes=writes)
        return controllers
