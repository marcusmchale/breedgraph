import pytest
from datetime import datetime, timezone

from breedgraph.adapters.files import JsonLinesErasureLog
from breedgraph.service_layer.infrastructure.erasure_log import ErasureLogEntry


@pytest.mark.asyncio
async def test_append_and_read(tmp_path):
    erasure_log = JsonLinesErasureLog(tmp_path / 'logs' / 'person_erasure_log.jsonl')
    assert erasure_log.read() == []

    entries = [
        ErasureLogEntry(person_id=1, erased_at=datetime(2026, 1, 1, tzinfo=timezone.utc)),
        ErasureLogEntry(person_id=2, erased_at=datetime(2026, 2, 1, 12, 30, tzinfo=timezone.utc))
    ]
    for entry in entries:
        await erasure_log.append(entry)

    assert erasure_log.read() == entries
    # one line per entry, IDs and times only
    lines = erasure_log.path.read_text().splitlines()
    assert lines[0] == '{"person_id": 1, "erased_at": "2026-01-01T00:00:00+00:00"}'
