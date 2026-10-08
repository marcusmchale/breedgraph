"""
A record of erased Persons, kept outside the database, so erasures can be applied again
after restoring a backup taken before them. Entries hold IDs and times only, no personal data.
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


class AbstractErasureLog(ABC):

    @abstractmethod
    async def append(self, entry: ErasureLogEntry) -> None:
        ...

    @abstractmethod
    def read(self) -> List[ErasureLogEntry]:
        ...
