from neo4j import AsyncTransaction
from breedgraph.service_layer.infrastructure.dependency_guards import AbstractDependencyGuards
from breedgraph.adapters.neo4j.cypher import queries

class Neo4jDependencyGuards(AbstractDependencyGuards):

    def __init__(self, tx: AsyncTransaction):
        self.tx = tx

    async def reference_in_use(self, reference_id: int) -> bool:
        query = queries['guards']['reference_in_use']
        result = await self.tx.run(query, reference_id=reference_id)
        record = await result.single()
        return record.get('in_use')

    async def study_has_datasets(self, study_id: int) -> bool:
        query = queries['guards']['study_has_datasets']
        result = await self.tx.run(query, study_id=study_id)
        record = await result.single()
        return record.get('in_use')

    async def germplasm_has_units(self, germplasm_id: int) -> bool:
        query = queries['guards']['germplasm_has_units']
        result = await self.tx.run(query, germplasm_id=germplasm_id)
        record = await result.single()
        return record.get('in_use')