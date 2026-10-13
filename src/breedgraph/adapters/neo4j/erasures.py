from dataclasses import dataclass
from typing import Iterable

from breedgraph.adapters.neo4j.cypher import queries
from breedgraph.service_layer.infrastructure.driver import AbstractAsyncDriver
from breedgraph.service_layer.infrastructure.erasure_log import ErasureLogEntry, AccountDeletionLogEntry, LogEntry


@dataclass(frozen=True)
class AppliedErasures:
    persons: int
    accounts: int


async def apply_erasures(driver: AbstractAsyncDriver, entries: Iterable[LogEntry]) -> AppliedErasures:
    """
    Erase again every Person, and delete again every account, in the erasure log.
    Returns the number of Persons found, and of accounts not already deleted.
    Entries for records not in the database, e.g. created after the backup was taken, are skipped.
    """
    entries = list(entries)
    erasures = [
        {'person_id': entry.person_id, 'erased_at': entry.erased_at.isoformat()}
        for entry in entries if isinstance(entry, ErasureLogEntry)
    ]
    deletions = [
        {'user_id': entry.user_id, 'deleted_at': entry.deleted_at.isoformat()}
        for entry in entries if isinstance(entry, AccountDeletionLogEntry)
    ]
    persons = accounts = 0
    async with driver.session() as session:
        async with await session.begin_transaction() as tx:
            if erasures:
                result = await tx.run(queries['people']['apply_erasures'], erasures=erasures)
                persons = (await result.single())['erased']
            if deletions:
                result = await tx.run(queries['accounts']['delete_users'], deletions=deletions)
                accounts = (await result.single())['deleted']
            await tx.commit()
    return AppliedErasures(persons=persons, accounts=accounts)
