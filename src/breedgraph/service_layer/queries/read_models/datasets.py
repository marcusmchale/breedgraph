from dataclasses import dataclass, field
from numpy import datetime64
from typing import List

@dataclass
class DatasetSummary:
    """
    A readable dataset of a study and what its records span. Only the fields asked of the view are read:
    the others keep their defaults.
    """
    id: int
    concept_id: int
    subject_ids: List[int] = field(default_factory=list)
    location_ids: List[int] = field(default_factory=list)
    unit_root_ids: List[int] = field(default_factory=list)
    unit_count: int|None = None
    record_count: int|None = None
    start: datetime64|None = None
    end: datetime64|None = None


    def __post_init__(self):
        if self.start is not None:
            self.start = datetime64(self.start)
        if self.end is not None:
            self.end = datetime64(self.end)


@dataclass
class DatasetRead:
    """
    A dataset as the datasets view returns it: the header without its records, which are paged separately. A dataset
    the user cannot read, asked for by id, is a placeholder: its id, with no study, concept or records
    """
    id: int
    study: int | None
    concept: int | None
    contributors: List[int]
    references: List[int]
    record_count: int

    @property
    def redacted(self) -> bool:
        """Whether this is a placeholder: every stored dataset has a concept"""
        return self.concept is None


@dataclass
class DatasetsUnit:
    """
    A unit some datasets have records for, at it or below it: one node of the tree of units that matter to those
    datasets, with how many units at or below it have records, how many records that is, and whether any of those
    units lies below it
    """
    id: int
    unit_count: int
    record_count: int
    has_children: bool


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
