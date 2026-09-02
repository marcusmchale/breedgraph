from dataclasses import dataclass
from enum import Enum
from numpy import datetime64

class TermRepresentationType(str, Enum):
    """Matching GraphQL TermRepresentationType"""
    CONTINUOUS = "CONTINUOUS"
    CATEGORICAL = "CATEGORICAL"
    ORDINAL = "ORDINAL"

class AnalysisTermType(str, Enum):
    """Enum for term types matching GraphQL AnalysisTermType"""
    CONCEPT = "CONCEPT"
    TIME = "TIME"
    GERMPLASM = "GERMPLASM"
    UNIT_GROUP = "UNIT_GROUP"
    POSITION_GROUP = "POSITION_GROUP"

class TermTransformation(str, Enum):
    """Matching GraphQL TermTransformation"""
    CENTER = "CENTER"
    STANDARDIZE = "STANDARDIZE"
    LOG = "LOG"
    LOG1P = "LOG1P"
    SQRT = "SQRT"
    RECIPROCAL = "RECIPROCAL"

class TermAggregation(str, Enum):
    """Matching GraphQL TermAggregation"""
    NONE = "NONE"
    MEAN = "MEAN"
    MEDIAN = "MEDIAN"
    MIN = "MIN"
    MAX = "MAX"
    SUM = "SUM"
    COUNT = "COUNT"
    MODE = "MODE"

class TermEffect(str, Enum):
    """Matching GraphQL TermEffect"""
    FIXED = "FIXED"
    RANDOM = "RANDOM"

@dataclass
class AnalysisTermReference:
    """Identifies a term used by analysis"""
    type: AnalysisTermType
    concept_id: int|None = None  # Only set when type == CONCEPT

    def __post_init__(self):
        if self.type == AnalysisTermType.CONCEPT:
            if self.concept_id is None:
                raise ValueError("Concept ID should be provided for concept terms")
        else:
            if self.concept_id is not None:
                raise ValueError("Concept ID should not be provided for concept terms")

@dataclass
class AnalysisTerm:
    """A resolved analysis term"""
    reference: AnalysisTermReference
    representation: TermRepresentationType|None = None
    binning: dict|None = None  # Binning config, structure TBD
    level_order: list[str]|None = None
    transformations: list[TermTransformation]|None = None
    aggregation: TermAggregation|None = None
    effect: TermEffect|None = None
    random_slope_terms: list[AnalysisTermReference]|None = None

@dataclass
class InteractionTerm:
    """Terms participating in an interaction"""
    terms: list[AnalysisTermReference]


@dataclass
class DatetimeRangeExclusion:
    """Represents a datetime range for excluding records"""
    start: datetime64|None = None  # None means unbounded start
    end: datetime64|None = None  # None means unbounded end

    def __post_init__(self):
        if (self.start is not None and self.end is not None and
                self.start >= self.end):
            raise ValueError(
                f"Datetime range start ({self.start}) must be "
                f"before end ({self.end})"
            )

    def overlaps_with(
            self,
            record_start: datetime64|None,
            record_end: datetime64|None
    ) -> bool:
        """
        Check if this range overlaps with a record's time span.

        Uses standard interval overlap logic:
        overlap = range.start < record.end AND range.end > record.start

        None values are treated as unbounded:
        - None start means -infinity
        - None end means +infinity
        """
        # range.start < record.end (or range.start is unbounded)
        if self.start is not None and record_end is not None:
            if self.start >= record_end:
                return False

        # range.end > record.start (or range.end is unbounded)
        if self.end is not None and record_start is not None:
            if self.end <= record_start:
                return False

        return True


@dataclass
class DatetimeRangeExclusionList:
    """Manages multiple datetime range exclusions"""
    ranges: list[DatetimeRangeExclusion]

    def should_exclude_record(
            self,
            record_start: datetime64|None,
            record_end: datetime64|None
    ) -> bool:
        """
        Return True if record overlaps with ANY exclusion range.

        A record with no time data is never excluded by datetime ranges.
        """
        if record_start is None and record_end is None:
            return False

        return any(
            range_excl.overlaps_with(record_start, record_end)
            for range_excl in self.ranges
        )