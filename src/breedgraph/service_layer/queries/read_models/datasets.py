from dataclasses import dataclass
from numpy import datetime64
from typing import List

@dataclass
class DatasetSummary:
    id: int
    concept_id: int
    subject_ids: List[int]
    location_ids: List[int]
    block_ids: List[int]
    unit_count: int
    record_count: int
    start: datetime64|None = None
    end: datetime64|None = None


    def __post_init__(self):
        if self.start is not None:
            self.start = datetime64(self.start)
        if self.end is not None:
            self.end = datetime64(self.end)


@dataclass
class DatasetRead:
    """A dataset as the datasets view returns it: the header without its records, which are paged separately"""
    id: int
    study: int | None
    concept: int | None
    contributors: List[int]
    references: List[int]
    record_count: int
    readable: bool
