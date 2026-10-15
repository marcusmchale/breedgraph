"""
Replaying the erasure log after a restore (docs/person.md §5): each entry is applied to the record with its id and
creation time only, and the id counters are advanced past the logged ids so they are not issued again.
"""
from datetime import datetime, timezone

import pytest

from breedgraph.adapters.files import JsonLinesErasureLog
from breedgraph.adapters.neo4j.erasures import replay_erasure_log
from breedgraph.service_layer.infrastructure.erasure_log import ErasureLogEntry


async def run(driver, query, **parameters):
    async with driver.session() as session:
        result = await session.run(query, **parameters)
        return [record.data() async for record in result]


async def person_name(driver, person_id):
    return (await run(driver, "MATCH (p:Person {id: $id}) RETURN p.name AS name", id=person_id))[0]['name']


@pytest.mark.asyncio(loop_scope="session")
async def test_the_logged_person_is_erased(uow_factory, tmp_path):
    driver = uow_factory.driver
    person_id = (await run(driver, """
        MERGE (c:Counter {name: 'person'}) ON CREATE SET c.count = 0
        SET c.count = c.count + 1
        CREATE (p:Person {id: c.count, name: 'To erase', recorded_at: datetime('2026-01-01T09:30:00.123456Z')})
        RETURN p.id AS id
    """))[0]['id']
    log = JsonLinesErasureLog(tmp_path / 'log.jsonl')
    await log.append(ErasureLogEntry(
        person_id=person_id, erased_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        created_at=datetime(2026, 1, 1, 9, 30, 0, 123456, tzinfo=timezone.utc)
    ))
    replay = await replay_erasure_log(driver, log)
    assert (replay.applied.persons, replay.applied.reissued_persons) == (1, ())
    assert await person_name(driver, person_id) is None


@pytest.mark.asyncio(loop_scope="session")
async def test_an_id_given_again_after_a_restore_is_not_erased(uow_factory, tmp_path):
    """
    A Person created and erased after a backup; the backup is restored, rolling the id counter back,
    and the next Person created is given the erased one's id. Replaying the log leaves the new Person alone,
    and advances the counter so the id is not given out again.
    """
    driver = uow_factory.driver
    before = (await run(driver, "MERGE (c:Counter {name: 'person'}) ON CREATE SET c.count = 0 RETURN c.count AS count"))[0]['count']
    erased_id = before + 1
    log = JsonLinesErasureLog(tmp_path / 'log.jsonl')
    await log.append(ErasureLogEntry(
        person_id=erased_id, erased_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)
    ))

    # restored from the backup: the counter is where it was, and a new Person is given the same id
    await run(driver, """
        MATCH (c:Counter {name: 'person'}) SET c.count = $before + 1
        CREATE (:Person {id: $before + 1, name: 'Someone new', recorded_at: datetime('2026-03-01T10:00:00Z')})
    """, before=before)

    replay = await replay_erasure_log(driver, log)
    assert replay.applied.reissued_persons == (erased_id,)
    assert await person_name(driver, erased_id) == 'Someone new'

    # restored again, before anyone new was created: the counter moves past the logged id
    await run(driver, "MATCH (p:Person {id: $id}) DETACH DELETE p WITH 1 AS x MATCH (c:Counter {name: 'person'}) SET c.count = $before",
              id=erased_id, before=before)
    replay = await replay_erasure_log(driver, log)
    assert replay.counters['person'] == erased_id


@pytest.mark.asyncio(loop_scope="session")
async def test_another_database_records_are_left_alone(uow_factory, tmp_path):
    """A log replayed onto another database's dump, e.g. a test database: its records were created at other times"""
    driver = uow_factory.driver
    person_id = (await run(driver, """
        MERGE (c:Counter {name: 'person'}) ON CREATE SET c.count = 0
        SET c.count = c.count + 1
        CREATE (p:Person {id: c.count, name: 'Test person', recorded_at: datetime('2026-05-05T05:05:05Z')})
        RETURN p.id AS id
    """))[0]['id']
    log = JsonLinesErasureLog(tmp_path / 'log.jsonl')
    await log.append(ErasureLogEntry(
        person_id=person_id, erased_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)
    ))
    replay = await replay_erasure_log(driver, log)
    assert (replay.applied.persons, replay.applied.reissued_persons) == (0, (person_id,))
    assert await person_name(driver, person_id) == 'Test person'


@pytest.mark.asyncio(loop_scope="session")
async def test_entries_without_a_creation_time_are_skipped(uow_factory, tmp_path):
    driver = uow_factory.driver
    person_id = (await run(driver, """
        MERGE (c:Counter {name: 'person'}) ON CREATE SET c.count = 0
        SET c.count = c.count + 1
        CREATE (p:Person {id: c.count, name: 'Kept', recorded_at: datetime()})
        RETURN p.id AS id
    """))[0]['id']
    log = JsonLinesErasureLog(tmp_path / 'log.jsonl')
    log.path.write_text(f'{{"person_id": {person_id}, "erased_at": "2026-01-01T00:00:00+00:00"}}\n')
    replay = await replay_erasure_log(driver, log)
    assert (replay.entries, replay.untimed, replay.applied.persons) == (0, 1, 0)
    assert await person_name(driver, person_id) == 'Kept'
