from dataclasses import dataclass, field
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


@dataclass
class GroupingCodes:
    """The codes of one record grouping that a dataset's records carry, in text order"""
    grouping_id: int
    codes: List[str]


@dataclass
class DatasetDimensions:
    """
    What a dataset's records span, read without the records: counts, the time range, the record times and values
    at each percentile from 0 to 100 (an empty list when no record has one), and the record group codes by grouping.
    Pickers and binning suggestions work from this instead of loading every record.
    """
    record_count: int
    unit_count: int
    start: datetime64 | None = None
    end: datetime64 | None = None
    time_percentiles: List[datetime64] = field(default_factory=list)
    value_percentiles: List[str] = field(default_factory=list)
    groups: List[GroupingCodes] = field(default_factory=list)

    def __post_init__(self):
        if self.start is not None:
            self.start = datetime64(self.start)
        if self.end is not None:
            self.end = datetime64(self.end)
