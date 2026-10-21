from neo4j import AsyncResult, AsyncSession
from numpy import datetime64
from typing import List, Dict, Tuple

from breedgraph.adapters.neo4j.cypher.query_builders import unit_graphs as unit_graph_queries
from breedgraph.domain.model.unit_graphs import UnitOutput, UnitArrival, Position, arrival_key
from breedgraph.domain.model.controls import ReadRelease
from breedgraph.domain.model.time_descriptors import deserialize_time, serialize_npdt64
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

    async def _get_inherited_germplasm(self, unit_ids: List[int]) -> Dict[int, Tuple[int, int]]:
        result: AsyncResult = await self.session.run(
            unit_graph_queries.read_inherited_germplasm(),
            unit_ids=unit_ids, read_teams=self.read_teams, minimum_release=self.minimum_release
        )
        inherited = {}
        async for record in result:
            sources = record['sources']
            # none above, one hidden from the user (its germplasm unknown), or lineages that differ: nothing comes down
            if not sources or not all(source['readable'] for source in sources):
                continue
            if len({source['germplasm_id'] for source in sources}) != 1:
                continue
            nearest = min(sources, key=lambda source: (source['distance'], source['unit_id']))
            inherited[record['unit_id']] = (nearest['germplasm_id'], nearest['unit_id'])
        return inherited

    async def _get_arrivals(self, location_ids: List[int], unit_id: int | None) -> List[UnitArrival]:
        result: AsyncResult = await self.session.run(
            unit_graph_queries.read_unit_arrivals(related=unit_id is not None),
            location_ids=location_ids, unit_id=unit_id, read_teams=self.read_teams, minimum_release=self.minimum_release
        )
        return [
            UnitArrival(
                location_id=record['location_id'],
                start=deserialize_time(*record['start']),
                unit_count=record['unit_count'],
                root_ids=list(record['root_ids'])
            )
            async for record in result
        ]

    async def _get_arrival_units(
            self, location_id: int, start: datetime64 | None, unit_id: int | None, offset: int, limit: int
    ) -> List[UnitOutput]:
        return await self._read(
            unit_graph_queries.read_arrival_units(related=unit_id is not None),
            location_id=location_id, start=serialize_npdt64(start, to_neo4j=True), unit_id=unit_id,
            offset=offset, limit=limit
        )

    async def _get_arrival_units_by_subject(
            self, arrivals: List[Tuple[int, datetime64 | None]]
    ) -> Dict[Tuple[int, str | None], Dict[int | None, List[UnitOutput]]]:
        keys = {}
        for location_id, start in arrivals:
            keys[arrival_key(location_id, start)] = {
                'location_id': location_id, 'start': serialize_npdt64(start, to_neo4j=True)
            }
        result: AsyncResult = await self.session.run(
            unit_graph_queries.read_arrival_units_by_subject(),
            arrivals=list(keys.values()), read_teams=self.read_teams, minimum_release=self.minimum_release
        )
        found = {key: {} for key in keys}
        async for record in result:
            arrival = record['arrival']
            start = deserialize_time(arrival['start']['time'], arrival['start']['unit'], arrival['start']['step'])
            found[arrival_key(arrival['location_id'], start)][record['subject']] = [
                UnitOutput(id=unit['id'], name=unit['name'], subject=record['subject']) for unit in record['units']
            ]
        return found

    async def _get_arrival_unit_ids(self, location_id: int, start: datetime64 | None, unit_id: int | None) -> List[int]:
        result: AsyncResult = await self.session.run(
            unit_graph_queries.read_arrival_unit_ids(related=unit_id is not None),
            location_id=location_id, start=serialize_npdt64(start, to_neo4j=True), unit_id=unit_id,
            read_teams=self.read_teams, minimum_release=self.minimum_release
        )
        record = await result.single()
        return list(record['unit_ids']) if record else []
