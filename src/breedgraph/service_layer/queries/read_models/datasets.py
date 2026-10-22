from dataclasses import dataclass, field
from numpy import datetime64
from typing import List
from breedgraph.domain.model.contributions import Contribution, contributions_from

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


@dataclass
class DatasetRead:
    """
    A dataset as the datasets view returns it: the header without its records, which are paged separately. A dataset
    the user cannot read, asked for by id, is a placeholder: its id, with no study, concept or records
    """
    id: int
    study: int | None
    concept: int | None
    contributions: List[Contribution]
    references: List[int]
    record_count: int
    # the licence of the dataset's study, and whether the user reads the dataset or its study through a controlling
    # team, so need not accept it (docs/licences.md §5)
    licence: int | None = None
    licence_exempt: bool = False

    def __post_init__(self):
        self.contributions = contributions_from(self.contributions)

    @property
    def licence_required(self) -> bool:
        """Whether the user must accept the licence of the dataset's study to get its records"""
        return self.licence is not None and not self.licence_exempt

    @property
    def redacted(self) -> bool:
        """Whether this is a placeholder: every stored dataset has a concept"""
        return self.concept is None


@dataclass
class FileLicence:
    """The licence of a readable dataset citing a file, and whether the user is exempt from it for that dataset"""
    dataset_id: int
    licence_id: int
    exempt: bool


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
class DatasetPlaceLayout:
    """
    A layout of the positions placing the units of datasets at a location: how many of their recorded units it places,
    and the axis names a position in it has values on, its own and those of the layouts above it
    """
    layout_id: int
    unit_count: int
    axes: List[str] = field(default_factory=list)


@dataclass
class DatasetPlace:
    """
    A location of one of some location types that analysis position grouping could place the records of datasets
    at: how many of their recorded units it places, and the layouts of the positions placing them
    """
    location_id: int
    unit_count: int
    layouts: List[DatasetPlaceLayout] = field(default_factory=list)


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

