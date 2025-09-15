from typing import Dict, List, Any, Optional, AsyncGenerator, Tuple
from neo4j import AsyncTransaction, Record
from neo4j.time import DateTime as Neo4jDateTime

from src.breedgraph.domain.model.germplasm import GermplasmInput, GermplasmStored, Reproduction, GermplasmSourceType, GermplasmRelationship
from src.breedgraph.domain.model.time_descriptors import serialize_npdt64, deserialize_time, npdt64_to_neo4j
from src.breedgraph.service_layer.persistence.germplasm import GermplasmPersistenceService

from src.breedgraph.adapters.neo4j.cypher import queries

import logging

logger = logging.getLogger(__name__)

class Neo4jGermplasmPersistenceService(GermplasmPersistenceService):
    """
    Neo4j implementation of germplasm persistence service.
    Handles all database operations for germplasm entries and their relationships.
    """

    def __init__(self, tx: AsyncTransaction):
        self.tx = tx

    @staticmethod
    def record_to_entry(record: Record) -> GermplasmStored:
        """Convert a Neo4j record to a germplasm entry."""
        if record.get('entry') is not None:
            record = record.get('entry')

        record.pop('name_lower')
        if 'time' in record:
            record['time'] = deserialize_time(record['time'], unit = record.pop('time_unit'), step=record.pop('time_step'))
        if 'reproduction' in record:
            record['reproduction'] = Reproduction(record['reproduction'])
        return GermplasmStored(**record)

    async def _create_entry(self, entry: GermplasmInput) -> GermplasmStored:
        """Create a new germplasm entry in Neo4j."""
        query = queries['germplasm']['create_entry']
        params = entry.model_dump()
        params['name_lower'] = params['name'].casefold()
        serialized = serialize_npdt64(params['time'], to_neo4j=True)
        params.update({
            'time': serialized['time'],
            'time_unit': serialized['unit'],
            'time_step': serialized['step']
        })
        methods = params.pop('methods', [])
        references = params.pop('references', [])
        result = await self.tx.run(
            query, params = params, methods=methods, references=references
        )
        record = await result.single(strict=True)
        return self.record_to_entry(record)

    async def get_entry(self, entry_id: int = None, name: str = None) -> Optional[GermplasmStored]:
        """Retrieve a germplasm entry """
        if entry_id is not None:
            query = queries['germplasm']['get_entry_by_id']
        elif name is not None:
            query = queries['germplasm']['get_entry_by_name']
        else:
            return anext(self.get_entries())

        result = await self.tx.run(query, {'entry_id': entry_id, 'name': name})
        record = await result.single()
        if record:
            return self.record_to_entry(record)
        else:
            return None

    async def update_entry(self, entry: GermplasmStored) -> None:
        """Update an existing germplasm entry."""
        query = queries['germplasm']['set_entry']
        params = entry.model_dump()
        params['name_lower'] = params['name'].casefold()
        serialized = serialize_npdt64(params['time'], to_neo4j=True)
        params.update({
            'time': serialized['time'],
            'time_unit': serialized['unit'],
            'time_step': serialized['step']
        })
        if params.get('reproduction') is not None:
            params.update({'reproduction': params['reproduction'].name})
        entry_id = params.pop('id')
        methods = params.pop('methods', [])
        references = params.pop('references', [])
        await self.tx.run(query, props = params, entry_id = entry_id, methods=methods, references=references)

    async def get_entries(
            self,
            entry_ids: List[int] | None = None,
            names: List[str] | None = None
    ) -> AsyncGenerator[GermplasmStored, None]:

        """Retrieve all germplasm entries with optional filtering."""
        if entry_ids:
            query = queries['germplasm']['get_entries_by_id']
            params = {'entry_ids': entry_ids}
        elif names:
            query = queries['germplasm']['get_entries_by_name']
            params = {'names_lower': [name.casefold() for name in names]}
        else:
            query = queries['germplasm']['get_all_entries']
            params = None

        result = await self.tx.run(query, params)
        async for record in result:
            yield self.record_to_entry(record)

    # Validation query methods
    async def name_in_use(self, name: str, exclude_id: int | None = None) -> bool:
        """Check if a name is already in use."""
        async for entry in self.get_entries(names=[name]):
            if entry.id != exclude_id:
                return True
        return False

    async def entries_exist(self, entry_ids: List[int]) -> Dict[int, bool]:
        """Batch check if germplasm entries exist."""
        entry_existence = {}
        async for entry in self.get_entries(entry_ids=entry_ids):
            entry_existence[entry.id] = True
        return entry_existence

    # Relationship operations
    async def create_relationships(self, relationships: List[GermplasmRelationship]) -> None:
        """Create relationships between germplasm entries."""
        # convert enum to string for storage in neo4j
        relationships_dump = [
            relationship.model_dump() for relationship in relationships
        ]
        query = queries['germplasm']['create_relationships']
        await self.tx.run(query, relationships=relationships_dump)

    async def get_relationships(self, entry_id: int) -> AsyncGenerator[GermplasmRelationship, None]:
        """Get all relationships for a germplasm entry."""
        query = queries['germplasm']['get_relationships']
        result = await self.tx.run(query, entry_id=entry_id)
        async for record in result:
            yield GermplasmRelationship(**record)

    async def get_source_relationships(self, entry_id: int) -> AsyncGenerator[GermplasmRelationship, None]:
        """Get all source relationships for a germplasm entry."""
        query = queries['germplasm']['get_source_relationships']
        result = await self.tx.run(query, entry_id=entry_id)
        async for record in result:
            yield GermplasmRelationship(**record)

    async def get_target_relationships(self, entry_id: int) -> AsyncGenerator[GermplasmRelationship, None]:
        """Get all target relationships for a germplasm entry."""
        query = queries['germplasm']['get_target_relationships']
        result = await self.tx.run(query, entry_id=entry_id)
        async for record in result:
            yield GermplasmRelationship(**record)

    async def get_root_entries(self) -> AsyncGenerator[GermplasmStored, None]:
        raise NotImplementedError

    async def get_ancestor_ids(self, entry_id: int, path_length_limit=None) -> List[int]:
        if path_length_limit:
            query = queries['germplasm']['get_ancestor_ids_with_limit']
            result = await self.tx.run(query, entry_id=entry_id, limit=path_length_limit)
        else:
            query = queries['germplasm']['get_ancestor_ids']
            result = await self.tx.run(query, entry_id=entry_id, limit=path_length_limit)
        return [record['ancestor.id'] async for record in result]

    async def get_descendant_ids(self, entry_id: int, path_length_limit=None) -> List[int]:
        if path_length_limit:
            query = queries['germplasm']['get_descendant_ids_with_limit']
            result = await self.tx.run(query, entry_id=entry_id, limit=path_length_limit)
        else:
            query = queries['germplasm']['get_descendant_ids']
            result = await self.tx.run(query, entry_id=entry_id, limit=path_length_limit)
        return [record['descendant.id'] async for record in result]

    async def has_path(self, source_id: int, target_id: int) -> bool:
        """Check if there's a path between two entries (for cycle detection)."""
        query = queries['germplasm']['has_path_between_entries']
        result = await self.tx.run(query, source_id=source_id, target_id=target_id)
        record = await result.single()
        return record['has_path']
