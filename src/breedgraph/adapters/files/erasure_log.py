import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List

from breedgraph import config
from breedgraph.service_layer.infrastructure.erasure_log import (
    AbstractErasureLog, ErasureLogEntry, AccountDeletionLogEntry, LogEntry
)


class JsonLinesErasureLog(AbstractErasureLog):
    """
    One JSON object per line, appended and flushed to disk for each erasure or account deletion.
    The path is read from config.PERSON_ERASURE_LOG_PATH unless given.
    """

    def __init__(self, path: str | Path | None = None):
        self._path = path

    @property
    def path(self) -> Path:
        return Path(self._path or config.PERSON_ERASURE_LOG_PATH)

    @staticmethod
    def _line(entry: LogEntry) -> str:
        if isinstance(entry, AccountDeletionLogEntry):
            record = {'user_id': entry.user_id, 'deleted_at': entry.deleted_at.isoformat()}
        else:
            record = {'person_id': entry.person_id, 'erased_at': entry.erased_at.isoformat()}
        if entry.created_at is not None:
            record['created_at'] = entry.created_at.isoformat()
        return json.dumps(record)

    async def append(self, entry: LogEntry) -> None:
        await asyncio.to_thread(self._append_line, self._line(entry))

    def _append_line(self, line: str) -> None:
        path = self.path
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'a', encoding='utf-8') as log_file:
            log_file.write(line + '\n')
            log_file.flush()
            os.fsync(log_file.fileno())

    def read(self) -> List[LogEntry]:
        if not self.path.exists():
            return []
        entries = []
        with open(self.path, encoding='utf-8') as log_file:
            for line in log_file:
                if line.strip():
                    record = json.loads(line)
                    created_at = datetime.fromisoformat(record['created_at']) if record.get('created_at') else None
                    if 'user_id' in record:
                        entries.append(AccountDeletionLogEntry(
                            user_id=int(record['user_id']),
                            deleted_at=datetime.fromisoformat(record['deleted_at']),
                            created_at=created_at
                        ))
                    else:
                        entries.append(ErasureLogEntry(
                            person_id=int(record['person_id']),
                            erased_at=datetime.fromisoformat(record['erased_at']),
                            created_at=created_at
                        ))
        return entries
