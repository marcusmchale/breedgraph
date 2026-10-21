from typing import Dict, List, Set

from neo4j import AsyncTransaction
from numpy import datetime64

from breedgraph.domain.model.time_descriptors import serialize_npdt64, deserialize_time
from breedgraph.domain.model.unit_graphs import Position
from breedgraph.domain.services.unit_positions import UnitPositions, StoredPosition, PositionWrites
from breedgraph.service_layer.persistence.unit_positions import UnitPositionsPersistenceService

from breedgraph.adapters.neo4j.cypher.query_builders import unit_positions as position_queries
from breedgraph.adapters.neo4j.cypher.query_builders import unit_graphs as unit_graph_queries

import logging

logger = logging.getLogger(__name__)


def _time(record: dict, name: str):
    return deserialize_time(record.get(name), record.get(f'{name}_unit'), record.get(f'{name}_step'))


def _row(position: Position) -> dict:
    """A position as stored: its place, and each time with its unit and step"""
    row = {
        'location_id': position.location_id,
        'layout_id': position.layout_id,
        'coordinates': position.coordinates if position.coordinates else None
    }
    for name in ('start', 'end'):
        serialized = serialize_npdt64(getattr(position, name), to_neo4j=True)
        row |= {name: serialized['time'], f'{name}_unit': serialized['unit'], f'{name}_step': serialized['step']}
    return row


class Neo4jUnitPositionsPersistenceService(UnitPositionsPersistenceService):

    def __init__(self, tx: AsyncTransaction):
        self.tx = tx

    async def read_positions_locked(self, unit_ids: List[int]) -> Dict[int, UnitPositions]:
        result = await self.tx.run(position_queries.read_positions_locked(), unit_ids=unit_ids)
        found = {}
        async for record in result:
            found[record['unit_id']] = UnitPositions(
                unit_id=record['unit_id'],
                name=record['name'],
                root=record['root'],
                positions=[
                    StoredPosition(key=position['key'], position=Position(
                        location_id=position['location_id'],
                        layout_id=position['layout_id'],
                        coordinates=position.get('coordinates'),
                        start=_time(position, 'start'),
                        end=_time(position, 'end')
                    ))
                    for position in record['positions']
                ]
            )
        return found

    async def write(self, writes: PositionWrites) -> None:
        if writes.deleted:
            await self._run(position_queries.delete_positions(), len(writes.deleted), keys=writes.deleted)
        if writes.changed:
            rows = [_row(position) | {'key': key} for key, position in writes.changed]
            await self._run(position_queries.change_positions(), len(rows), rows=rows)
        if writes.created:
            rows = [_row(position) | {'unit_id': unit_id} for unit_id, position in writes.created]
            await self._run(position_queries.create_positions(), len(rows), rows=rows)

    async def _run(self, query: str, expected: int, **parameters) -> None:
        result = await self.tx.run(query, **parameters)
        record = await result.single()
        if record['written'] != expected:
            # a unit, location or position read in this transaction is gone: nothing is written
            raise ValueError(f"Expected to write {expected} positions, but wrote {record['written']}")

    async def arrival_unit_ids(
            self,
            location_id: int,
            start: datetime64 | None,
            unit_id: int | None,
            read_teams: Set[int],
            minimum_release: int
    ) -> List[int]:
        result = await self.tx.run(
            unit_graph_queries.read_arrival_unit_ids(related=unit_id is not None),
            location_id=location_id, start=serialize_npdt64(start, to_neo4j=True), unit_id=unit_id,
            read_teams=list(read_teams), minimum_release=minimum_release
        )
        record = await result.single()
        return sorted(record['unit_ids']) if record else []
