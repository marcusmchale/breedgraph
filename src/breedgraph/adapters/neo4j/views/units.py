from neo4j import AsyncResult, AsyncSession
from typing import List, Dict

from breedgraph.adapters.neo4j.cypher.query_builders import unit_graphs as unit_graph_queries
from breedgraph.domain.model.unit_graphs import UnitOutput, Position
from breedgraph.domain.model.controls import ReadRelease
from breedgraph.domain.model.time_descriptors import deserialize_time
from breedgraph.service_layer.queries.views.units import AbstractUnitsView


class Neo4jUnitsView(AbstractUnitsView):
    """
    Units read by id or by location, with the read check and redaction in Cypher rather than by loading the unit graph
    (see query_builders.unit_graphs): readable units in full, their parents and children the nearest readable units, as
    UnitGraph.redacted reconnects them, and placeholders for hidden units asked for by id and hidden unit graph roots holding
    readable units.
    """

    def __init__(self, session: AsyncSession, user_id: int | None, read_teams: List[int]):
        self.session = session
        self.user_id = user_id
        self.read_teams = read_teams

    @property
    def minimum_release(self) -> int:
        return int(ReadRelease.PUBLIC if self.user_id is None else ReadRelease.REGISTERED)

    @staticmethod
    def _positions(record: dict) -> List[Position]:
        positions = []
        for position in record.get('positions') or []:
            position['start'] = deserialize_time(position.get('start'), position.pop('start_unit', None), position.pop('start_step', None))
            position['end'] = deserialize_time(position.get('end'), position.pop('end_unit', None), position.pop('end_step', None))
            positions.append(Position(**position))
        return positions

    def _to_unit(self, record: dict) -> UnitOutput:
        if 'positions' in record:
            record['positions'] = self._positions(record)
        return UnitOutput(**record)

    async def _read(self, query: str, **params) -> List[UnitOutput]:
        result: AsyncResult = await self.session.run(
            query, **params, read_teams=self.read_teams, minimum_release=self.minimum_release
        )
        return [self._to_unit(dict(record['unit'])) async for record in result]

    async def _get_unit_names(self, unit_ids: List[int]) -> Dict[int, UnitOutput]:
        units = await self._read(unit_graph_queries.read_unit_names(), unit_ids=unit_ids)
        return {unit.id: unit for unit in units}

    async def _get_ancestor_ids(self, unit_ids: List[int]) -> Dict[int, List[int]]:
        result: AsyncResult = await self.session.run(
            unit_graph_queries.read_unit_ancestors(),
            unit_ids=unit_ids, read_teams=self.read_teams, minimum_release=self.minimum_release
        )
        return {record['unit_id']: list(record['ancestor_ids']) async for record in result}

    async def _get_descendants_by_subject(self, unit_ids: List[int]) -> Dict[int | None, List[UnitOutput]]:
        async with await self.session.begin_transaction() as tx:
            result: AsyncResult = await tx.run(
                unit_graph_queries.read_descendants_by_subject(),
                unit_ids=unit_ids,
                read_teams=self.read_teams,
                minimum_release=self.minimum_release
            )
            return {
                record['subject']: [
                    UnitOutput(id=unit['id'], name=unit['name'], subject=record['subject']) for unit in record['units']
                ]
                async for record in result
            }

    async def _get_units(self, unit_ids: List[int]) -> Dict[int, UnitOutput]:
        units = await self._read(unit_graph_queries.read_units(), unit_ids=unit_ids)
        return {unit.id: unit for unit in units}

    async def _get_unit_graph_roots(self, location_ids: List[int]) -> List[UnitOutput]:
        return await self._read(unit_graph_queries.read_unit_graph_roots(), location_ids=location_ids)
