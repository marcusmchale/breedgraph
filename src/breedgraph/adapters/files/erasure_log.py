import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List

from breedgraph import config
from breedgraph.service_layer.infrastructure.erasure_log import AbstractErasureLog, ErasureLogEntry


class JsonLinesErasureLog(AbstractErasureLog):
    """
    One JSON object per line, appended and flushed to disk for each erasure.
    The path is read from config.PERSON_ERASURE_LOG_PATH unless given.
    """

    def __init__(self, path: str | Path | None = None):
        self._path = path

    @property
    def path(self) -> Path:
        return Path(self._path or config.PERSON_ERASURE_LOG_PATH)

    async def append(self, entry: ErasureLogEntry) -> None:
        line = json.dumps({'person_id': entry.person_id, 'erased_at': entry.erased_at.isoformat()})
        await asyncio.to_thread(self._append_line, line)

    def _append_line(self, line: str) -> None:
        path = self.path
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'a', encoding='utf-8') as log_file:
            log_file.write(line + '\n')
            log_file.flush()
            os.fsync(log_file.fileno())

    def read(self) -> List[ErasureLogEntry]:
        if not self.path.exists():
            return []
        entries = []
        with open(self.path, encoding='utf-8') as log_file:
            for line in log_file:
                if line.strip():
                    record = json.loads(line)
                    entries.append(ErasureLogEntry(
                        person_id=int(record['person_id']),
                        erased_at=datetime.fromisoformat(record['erased_at'])
                    ))
        return entries
