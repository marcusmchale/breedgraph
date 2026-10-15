"""
A record of erased Persons and deleted accounts, kept outside the database, so they can be applied again
after restoring a backup taken before them, including those made after the backup. It is one file, only ever appended
to. Entries hold IDs and times only, no personal data, among them when the Person or account was created, so a replay
erases that one and never another given the same id (after a restore, or in another database's dump).
See docs/person.md §5.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List


@dataclass(frozen=True)
class ErasureLogEntry:
    person_id: int
    erased_at: datetime
    # when the Person was created: a replay erases the Person with this id and creation time only
    created_at: datetime | None = None


@dataclass(frozen=True)
class AccountDeletionLogEntry:
    user_id: int
    deleted_at: datetime
    created_at: datetime | None = None  # when the account was created, as for ErasureLogEntry


LogEntry = ErasureLogEntry | AccountDeletionLogEntry


class AbstractErasureLog(ABC):

    @abstractmethod
    async def append(self, entry: LogEntry) -> None:
        ...

    @abstractmethod
    def read(self) -> List[LogEntry]:
        ...
