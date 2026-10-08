from typing import Iterable

from breedgraph.adapters.neo4j.cypher import queries
from breedgraph.service_layer.infrastructure.driver import AbstractAsyncDriver
from breedgraph.service_layer.infrastructure.erasure_log import ErasureLogEntry


async def apply_person_erasures(driver: AbstractAsyncDriver, entries: Iterable[ErasureLogEntry]) -> int:
    """
    Erase again every Person in the erasure log. Returns the number of Persons found.
    Entries for Persons not in the database, e.g. created after the backup was taken, are skipped.
    """
    erasures = [
        {'person_id': entry.person_id, 'erased_at': entry.erased_at.isoformat()}
        for entry in entries
    ]
    if not erasures:
        return 0
    async with driver.session() as session:
        async with await session.begin_transaction() as tx:
            result = await tx.run(queries['people']['apply_erasures'], erasures=erasures)
            record = await result.single()
            await tx.commit()
    return record['erased']
