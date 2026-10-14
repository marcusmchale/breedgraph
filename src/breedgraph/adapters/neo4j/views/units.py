from neo4j import AsyncResult, AsyncSession
from typing import List, Dict

from breedgraph.adapters.neo4j.cypher import queries
from breedgraph.domain.model.blocks import UnitOutput, Position
from breedgraph.domain.model.controls import ReadRelease, ControlledModel
from breedgraph.domain.model.time_descriptors import deserialize_time
from breedgraph.service_layer.queries.views.units import AbstractUnitsView


class Neo4jUnitsView(AbstractUnitsView):
    """Units read by id or by location, with the read check done in Cypher rather than by loading the block"""

    def __init__(self, session: AsyncSession, user_id: int | None, read_teams: List[int]):
        self.session = session
        self.user_id = user_id
        self.read_teams = read_teams

    @property
    def minimum_release(self) -> int:
        return int(ReadRelease.PUBLIC if self.user_id is None else ReadRelease.REGISTERED)

    @staticmethod
    def record_to_unit(record: dict) -> UnitOutput:
        readable = record.pop('readable', True)
        positions = []
        for position in record.get('positions') or []:
            position['start'] = deserialize_time(position.get('start'), position.pop('start_unit', None), position.pop('start_step', None))
            position['end'] = deserialize_time(position.get('end'), position.pop('end_unit', None), position.pop('end_step', None))
            positions.append(Position(**position))
        record['positions'] = positions
        unit = UnitOutput(**record)
        if not readable:
            # as UnitStored.redacted: keep the id and the structure, hide the content
            unit.name = unit.name and ControlledModel.redacted_str
            unit.description = unit.description and ControlledModel.redacted_str
            unit.subject = None
            unit.positions = []
        return unit

    async def _get_units(self, unit_ids: List[int]) -> Dict[int, UnitOutput]:
        async with await self.session.begin_transaction() as tx:
            result: AsyncResult = await tx.run(
                queries['blocks']['get_units_for_read_teams'],
                unit_ids=unit_ids,
                read_teams=self.read_teams,
                minimum_release=self.minimum_release
            )
            units = {}
            async for record in result:
                unit = self.record_to_unit(record['unit'])
                units[unit.id] = unit
            return units

    async def _get_block_roots(self, location_ids: List[int]) -> List[UnitOutput]:
        async with await self.session.begin_transaction() as tx:
            result: AsyncResult = await tx.run(
                queries['blocks']['get_block_roots_for_read_teams'],
                location_ids=location_ids,
                read_teams=self.read_teams,
                minimum_release=self.minimum_release
            )
            return [self.record_to_unit(record['unit']) async for record in result]
