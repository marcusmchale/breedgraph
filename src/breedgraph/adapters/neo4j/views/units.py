from neo4j import AsyncResult, AsyncSession
from typing import List, Dict, Set

from breedgraph.adapters.neo4j.cypher import queries
from breedgraph.domain.model.blocks import UnitOutput, Position
from breedgraph.domain.model.controls import ReadRelease, ControlledModel
from breedgraph.domain.model.time_descriptors import deserialize_time
from breedgraph.service_layer.queries.views.units import AbstractUnitsView


class Neo4jUnitsView(AbstractUnitsView):
    """
    Units read by id or by location, with the read check done in Cypher rather than by loading the block.

    The result matches what the repository gives after Block.redacted: units the user cannot read are removed from
    the block and their parents reconnected to their children, except a block's root, which is kept redacted.
    A requested unit that is hidden comes back as the bare placeholder the context loader used to make for it:
    the id and a REDACTED name, with no edges. The hidden units of a block are read once per view (per request).
    """

    def __init__(self, session: AsyncSession, user_id: int | None, read_teams: List[int]):
        self.session = session
        self.user_id = user_id
        self.read_teams = read_teams
        # unit id -> (parent ids, child ids), and the unit ids found unreadable, learned as neighbours are checked
        self._neighbours_by_id: Dict[int, tuple] = {}
        self._hidden: Set[int] = set()

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

    async def _neighbours(self, tx, unit_ids: List[int]) -> Dict[int, tuple]:
        """Direct parents and children of these units, as (parent ids, child ids), learning which are hidden"""
        to_fetch = [unit_id for unit_id in dict.fromkeys(unit_ids) if unit_id not in self._neighbours_by_id]
        if to_fetch:
            for unit_id in to_fetch:
                self._neighbours_by_id[unit_id] = ([], [])
            result: AsyncResult = await tx.run(
                queries['blocks']['get_unit_neighbours_for_read_teams'],
                unit_ids=to_fetch,
                read_teams=self.read_teams,
                minimum_release=self.minimum_release
            )
            async for record in result:
                self._neighbours_by_id[record['id']][record['direction']].append(record['neighbour_id'])
                if record['readable']:
                    self._hidden.discard(record['neighbour_id'])
                else:
                    self._hidden.add(record['neighbour_id'])
        return {unit_id: self._neighbours_by_id[unit_id] for unit_id in unit_ids}

    async def _collapse(self, tx, unit_id: int, ids: List[int], direction: int, roots: Set[int]) -> List[int]:
        """
        Replace hidden ids by what lies beyond them, in the given direction (0 parents, 1 children), as
        remove_node_and_reconnect does. Only hidden neighbours are looked up further, one query per level,
        so a block whose units are all readable costs nothing beyond the neighbour check of the unit itself.
        """
        result, seen, frontier = [], {unit_id}, list(ids)
        while frontier:
            frontier = [candidate for candidate in dict.fromkeys(frontier) if candidate not in seen]
            seen.update(frontier)
            hidden = [candidate for candidate in frontier if candidate in self._hidden and candidate not in roots]
            result.extend(candidate for candidate in frontier if candidate not in hidden)
            if not hidden:
                break
            beyond = await self._neighbours(tx, hidden)
            frontier = [neighbour for candidate in hidden for neighbour in beyond[candidate][direction]]
        return result

    async def _records_to_units(self, tx, records: List[dict]) -> List[UnitOutput]:
        units = []
        roots = {record['root_id'] for record in records if record.get('root_id') is not None}
        readable_ids = [record['id'] for record in records if record.get('readable', True) or record.get('root_id') == record['id']]
        await self._neighbours(tx, readable_ids)
        for record in records:
            readable = record.pop('readable', True)
            root_id = record.pop('root_id', None)
            if not readable and root_id != record['id']:
                # hidden, and not a root: the structure must not show it
                units.append(UnitOutput(id=record['id'], name=ControlledModel.redacted_str))
                continue
            record['positions'] = self._positions(record)
            record['parents'] = await self._collapse(tx, record['id'], record.get('parents') or [], 0, roots)
            record['children'] = await self._collapse(tx, record['id'], record.get('children') or [], 1, roots)
            unit = UnitOutput(**record)
            if not readable:
                # a hidden root stays, redacted, so the block keeps its root
                unit.name = unit.name and ControlledModel.redacted_str
                unit.description = unit.description and ControlledModel.redacted_str
                unit.subject = None
                unit.positions = []
            units.append(unit)
        return units

    async def _get_unit_names(self, unit_ids: List[int]) -> Dict[int, UnitOutput]:
        async with await self.session.begin_transaction() as tx:
            result: AsyncResult = await tx.run(
                queries['blocks']['get_unit_names_for_read_teams'],
                unit_ids=unit_ids,
                read_teams=self.read_teams,
                minimum_release=self.minimum_release
            )
            units = {}
            async for record in result:
                units[record['id']] = UnitOutput(
                    id=record['id'],
                    name=(record['name'] and ControlledModel.redacted_str) if not record['readable'] else record['name'],
                    germplasm=record['germplasm'] if record['readable'] else None
                )
            return units

    async def _get_descendants_by_subject(self, unit_ids: List[int]) -> Dict[int | None, List[UnitOutput]]:
        async with await self.session.begin_transaction() as tx:
            result: AsyncResult = await tx.run(
                queries['blocks']['get_descendants_by_subject_for_read_teams'],
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
        async with await self.session.begin_transaction() as tx:
            result: AsyncResult = await tx.run(
                queries['blocks']['get_units_for_read_teams'],
                unit_ids=unit_ids,
                read_teams=self.read_teams,
                minimum_release=self.minimum_release
            )
            records = [record['unit'] async for record in result]
            return {unit.id: unit for unit in await self._records_to_units(tx, records)}

    async def _get_block_roots(self, location_ids: List[int]) -> List[UnitOutput]:
        async with await self.session.begin_transaction() as tx:
            result: AsyncResult = await tx.run(
                queries['blocks']['get_block_roots_for_read_teams'],
                location_ids=location_ids,
                read_teams=self.read_teams,
                minimum_release=self.minimum_release
            )
            records = [record['unit'] async for record in result]
            return await self._records_to_units(tx, records)
