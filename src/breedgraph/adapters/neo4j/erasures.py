from dataclasses import dataclass
from typing import Iterable

from breedgraph.adapters.neo4j.cypher import queries
from breedgraph.service_layer.infrastructure.driver import AbstractAsyncDriver
from breedgraph.service_layer.infrastructure.erasure_log import (
    ErasureLogEntry, AccountDeletionLogEntry, LogEntry, AbstractErasureLog
)


@dataclass(frozen=True)
class AppliedErasures:
    persons: int
    accounts: int
    # ids now held by another Person or account than the one logged (created at another time), left alone
    reissued_persons: tuple[int, ...] = ()
    reissued_accounts: tuple[int, ...] = ()


# Ids whose record was created at another time than the one logged: given to another after a restore
REISSUED_PERSONS = """
    UNWIND $erasures AS erasure
    MATCH (person: Person {id: erasure.person_id})
    WHERE erasure.created_at IS NOT NULL AND person.recorded_at.epochMillis <> datetime(erasure.created_at).epochMillis
    RETURN collect(DISTINCT person.id) AS ids
"""
REISSUED_ACCOUNTS = """
    UNWIND $deletions AS deletion
    MATCH (user: User {id: deletion.user_id})
    WHERE deletion.created_at IS NOT NULL AND user.time.epochMillis <> datetime(deletion.created_at).epochMillis
    RETURN collect(DISTINCT user.id) AS ids
"""

# The id counters of Persons and accounts, so that no logged id is issued again (see advance_id_counters)
ADVANCE_COUNTER = """
    MERGE (counter: Counter {name: $name})
      ON CREATE SET counter.count = 0
    SET counter.count = CASE WHEN counter.count < $at_least THEN $at_least ELSE counter.count END
    RETURN counter.count AS count
"""


def _created(entry: LogEntry) -> str | None:
    return entry.created_at.isoformat() if entry.created_at is not None else None


async def apply_erasures(driver: AbstractAsyncDriver, entries: Iterable[LogEntry]) -> AppliedErasures:
    """
    Erase again every Person, and delete again every account, in the erasure log.
    Returns the number of Persons found, and of accounts not already deleted.
    Entries for records not in the database, e.g. created after the backup was taken, are skipped,
    as are ids now held by a record created at another time than the one logged (reported as reissued).
    """
    entries = list(entries)
    erasures = [
        {'person_id': entry.person_id, 'erased_at': entry.erased_at.isoformat(), 'created_at': _created(entry)}
        for entry in entries if isinstance(entry, ErasureLogEntry)
    ]
    deletions = [
        {'user_id': entry.user_id, 'deleted_at': entry.deleted_at.isoformat(), 'created_at': _created(entry)}
        for entry in entries if isinstance(entry, AccountDeletionLogEntry)
    ]
    persons = accounts = 0
    reissued_persons = reissued_accounts = ()
    async with driver.session() as session:
        async with await session.begin_transaction() as tx:
            if erasures:
                result = await tx.run(REISSUED_PERSONS, erasures=erasures)
                reissued_persons = tuple(sorted((await result.single())['ids']))
                result = await tx.run(queries['people']['apply_erasures'], erasures=erasures)
                persons = (await result.single())['erased']
            if deletions:
                result = await tx.run(REISSUED_ACCOUNTS, deletions=deletions)
                reissued_accounts = tuple(sorted((await result.single())['ids']))
                result = await tx.run(queries['accounts']['delete_users'], deletions=deletions)
                accounts = (await result.single())['deleted']
            await tx.commit()
    return AppliedErasures(
        persons=persons, accounts=accounts, reissued_persons=reissued_persons, reissued_accounts=reissued_accounts
    )


async def advance_id_counters(driver: AbstractAsyncDriver, entries: Iterable[LogEntry]) -> dict[str, int]:
    """
    Advances the Person and account id counters past every id in the entries. A restored backup has the counters
    of its time, so without this the next Person or account created would be given a logged id again, and a later
    replay would erase it. Returns the counters as they now are.
    """
    entries = list(entries)
    highest = {
        'person': max((e.person_id for e in entries if isinstance(e, ErasureLogEntry)), default=None),
        'user': max((e.user_id for e in entries if isinstance(e, AccountDeletionLogEntry)), default=None),
    }
    counters = {}
    async with driver.session() as session:
        async with await session.begin_transaction() as tx:
            for name, at_least in highest.items():
                if at_least is not None:
                    counters[name] = (await (await tx.run(ADVANCE_COUNTER, name=name, at_least=at_least)).single())['count']
            await tx.commit()
    return counters


@dataclass(frozen=True)
class Replay:
    applied: AppliedErasures
    entries: int
    untimed: int  # entries without a creation time, which can't be matched to their record: not applied
    counters: dict[str, int]  # the id counters, advanced past the logged ids


async def replay_erasure_log(driver: AbstractAsyncDriver, erasure_log: AbstractErasureLog) -> Replay:
    """
    Applies the erasure log again (docs/person.md §5): every entry, to the record with its id and creation time,
    then advances the id counters past the logged ids, so they are not issued again.
    Entries without a creation time are not applied, as the record they are for can't be told from another given its
    id; every entry has one since creation times were logged.
    """
    entries = erasure_log.read()
    timed = [entry for entry in entries if entry.created_at is not None]
    applied = await apply_erasures(driver, timed)
    counters = await advance_id_counters(driver, entries)
    return Replay(applied=applied, entries=len(timed), untimed=len(entries) - len(timed), counters=counters)
