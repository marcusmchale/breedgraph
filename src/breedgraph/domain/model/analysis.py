from dataclasses import dataclass, field
from enum import Enum
from numpy import datetime64

from breedgraph.domain.model.blocks import Position

class AnalysisType(str, Enum):
    """Matching GraphQL AnalysisType"""
    ANOVA = "ANOVA"
    MDS = "MDS"
    CORRELATION = "CORRELATION"
    DESCRIPTIVE_STATISTICS = "DESCRIPTIVE_STATISTICS"
    OUTLIER_DETECTION = "OUTLIER_DETECTION"

    @property
    def input_key(self) -> str:
        """Key of the analysis specific configuration in the stored AnalysisInput"""
        return self.value.lower()

    @property
    def input_field(self) -> str:
        """Name of the analysis specific configuration field in the GraphQL AnalysisInput"""
        head, *tail = self.input_key.split('_')
        return head + ''.join(part.title() for part in tail)

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
    UNIT = "UNIT"
    POSITION = "POSITION"
    RECORD_GROUP = "RECORD_GROUP"
    STUDY = "STUDY"

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

class TimeAssignment(str, Enum):
    """Matching GraphQL TimeAssignment"""
    START = "START"
    END = "END"
    MIDPOINT = "MIDPOINT"

class BinningBoundary(str, Enum):
    """Matching GraphQL BinningBoundary"""
    LEFT = "LEFT"
    RIGHT = "RIGHT"

class DistanceMetric(str, Enum):
    EUCLIDEAN = "EUCLIDEAN"
    MANHATTAN = "MANHATTAN"
    MINKOWSKI = "MINKOWSKI"

class CorrelationMethod(str, Enum):
    PEARSON = "PEARSON"
    SPEARMAN = "SPEARMAN"
    KENDALL = "KENDALL"

class OutlierDetectionMethod(str, Enum):
    Z_SCORE = "Z_SCORE"
    IQR = "IQR"
    MAHALANOBIS = "MAHALANOBIS"

class ClusteringMethod(str, Enum):
    KMEANS = "KMEANS"
    HIERARCHICAL = "HIERARCHICAL"

class SumOfSquaresType(str, Enum):
    TYPE_II = "TYPE_II"
    TYPE_III = "TYPE_III"

class DdfMethod(str, Enum):
    SATTERTHWAITE = "SATTERTHWAITE"
    KENWARD_ROGER = "KENWARD_ROGER"

class EstimatedMeansContrast(str, Enum):
    PAIRWISE = "PAIRWISE"
    TRT_VS_CTRL = "TRT_VS_CTRL"
    NONE = "NONE"

class PValueAdjustment(str, Enum):
    TUKEY = "TUKEY"
    BONFERRONI = "BONFERRONI"
    HOLM = "HOLM"
    SIDAK = "SIDAK"
    NONE = "NONE"


@dataclass(frozen=True)
class AnalysisTermReference:
    """Identifies a term used by analysis"""
    type: AnalysisTermType
    concept_id: int|None = None  # Only set when type == CONCEPT
    record_group_dimension: str|None = None  # Only set when type == RECORD_GROUP, name of the dimension

    def __post_init__(self):
        requires = {
            AnalysisTermType.CONCEPT: "concept_id",
            AnalysisTermType.RECORD_GROUP: "record_group_dimension",
        }
        required = requires.get(self.type)
        for attr in ("concept_id", "record_group_dimension"):
            value = getattr(self, attr)
            if attr == required and value is None:
                raise ValueError(f"{attr} is required for {self.type.value} terms")
            if attr != required and value is not None:
                raise ValueError(f"{attr} must not be provided for {self.type.value} terms")

    @property
    def label(self) -> str:
        """Unique label of the term within an analysis, used as a column name"""
        if self.type == AnalysisTermType.CONCEPT:
            return f"concept:{self.concept_id}"
        if self.type == AnalysisTermType.RECORD_GROUP:
            return f"record_group:{self.record_group_dimension}"
        return self.type.value.lower()

    def model_dump(self) -> dict:
        return {
            'type': self.type.value,
            'concept_id': self.concept_id,
            'record_group_dimension': self.record_group_dimension
        }


@dataclass
class Binning:
    """
    Boundaries are interpreted according to the type of the binned value.
    With N boundaries, N + 1 bins are created.
    """
    boundaries: list[str]
    labels: list[str]
    boundary: BinningBoundary

    def __post_init__(self):
        if len(self.labels) != len(self.boundaries) + 1:
            raise ValueError("Binning requires exactly one more label than boundaries")


@dataclass(frozen=True)
class RecordGroupMember:
    """
    A code of a record grouping.
    dataset_id identifies the scope for dataset-scoped groupings.
    """
    grouping_id: int
    code: str
    dataset_id: int|None = None

    def __post_init__(self):
        object.__setattr__(self, 'code', (self.code or '').strip())
        if not self.code:
            raise ValueError(f"A code is required for members of grouping {self.grouping_id}")

@dataclass
class RecordGroupLevel:
    """A level shared by codes from one or more record groupings."""
    label: str
    members: list[RecordGroupMember]

    def __post_init__(self):
        self.label = (self.label or '').strip()
        if not self.label:
            raise ValueError("A label is required for record group levels")
        if '|' in self.label:
            # reserved for nested level identifiers
            raise ValueError(f"Level label '{self.label}' must not contain '|'")
        if not self.members:
            raise ValueError(f"Level '{self.label}' requires at least one member")
        if len(set(self.members)) != len(self.members):
            raise ValueError(f"Level '{self.label}' lists a member more than once")

@dataclass
class RecordGroupDimension:
    """
    A record group dimension of analytical observation identity, possibly spanning studies.

    Levels are nested by default: each (grouping, scope, code) is distinct.
    Level definitions explicitly combine codes into shared levels;
    codes not included keep their nested identity.
    """
    name: str
    grouping_ids: list[int]
    levels: list[RecordGroupLevel] = field(default_factory=list)

    def __post_init__(self):
        self.name = (self.name or '').strip()
        if not self.name:
            raise ValueError("A name is required for record group dimensions")
        if not self.grouping_ids:
            raise ValueError(f"Dimension '{self.name}' requires at least one grouping")
        if len(set(self.grouping_ids)) != len(self.grouping_ids):
            raise ValueError(f"Dimension '{self.name}' lists a grouping more than once")

        labels = [level.label for level in self.levels]
        if len(set(labels)) != len(labels):
            raise ValueError(f"Level labels must be unique within dimension '{self.name}'")

        for level in self.levels:
            for member in level.members:
                if member.grouping_id not in self.grouping_ids:
                    raise ValueError(
                        f"Level '{level.label}' references grouping {member.grouping_id} "
                        f"which is not part of dimension '{self.name}'"
                    )

    @property
    def reference(self) -> AnalysisTermReference:
        return AnalysisTermReference(type=AnalysisTermType.RECORD_GROUP, record_group_dimension=self.name)


@dataclass(frozen=True)
class RecordGroupLevelKey:
    """
    Resolved nested level of a record group.

    Codes are only comparable within the same grouping and scope:
    scope is None for study-wide groupings, otherwise the dataset IDs
    of the DatasetScope as resolved when the analysis is processed.
    """
    grouping_id: int
    scope: frozenset[int]|None
    code: str

    @property
    def key(self) -> str:
        scope = "*" if self.scope is None else ",".join(map(str, sorted(self.scope)))
        return f"{self.grouping_id}|{scope}|{self.code}"


@dataclass
class AnalysisTerm:
    """A term used by an analysis"""
    reference: AnalysisTermReference
    representation: TermRepresentationType|None = None
    binning: Binning|None = None
    level_order: list[str]|None = None
    transformations: list[TermTransformation] = field(default_factory=list)
    aggregation: TermAggregation = TermAggregation.NONE
    effect: TermEffect|None = None
    random_slope_terms: list[AnalysisTermReference] = field(default_factory=list)

@dataclass
class InteractionTerm:
    """Terms participating in an interaction"""
    terms: list[AnalysisTermReference]


@dataclass
class TimeSpecification:
    assignment: TimeAssignment
    binning: Binning

@dataclass
class GermplasmGrouping:
    germplasm_ids: list[int]

@dataclass
class UnitGrouping:
    unit_ids: list[int]

@dataclass
class PositionGrouping:
    location_id: int
    layout_id: int|None = None
    axis_indexes: list[int]|None = None
    positions: list[Position]|None = None
    time: datetime64|None = None

@dataclass
class AnalysisGrouping:
    """Dimensions of analytical observation identity, in addition to the observation unit."""
    time: TimeSpecification|None = None
    germplasm: GermplasmGrouping|None = None
    unit: UnitGrouping|None = None
    position: PositionGrouping|None = None
    record_groups: list[RecordGroupDimension] = field(default_factory=list)

    def get_record_group_dimension(self, name: str) -> RecordGroupDimension|None:
        return next((d for d in self.record_groups if d.name == name), None)


def intervals_overlap(
        start: datetime64|None,
        end: datetime64|None,
        other_start: datetime64|None,
        other_end: datetime64|None
) -> bool:
    """
    Half-open interval overlap: start < other_end AND end > other_start.
    None values are unbounded.
    """
    if start is not None and other_end is not None and start >= other_end:
        return False
    if end is not None and other_start is not None and end <= other_start:
        return False
    return True


@dataclass(frozen=True)
class AxisValue:
    index: int
    value: str

@dataclass
class PositionExclusion:
    location_id: int
    layout_id: int|None = None  # None: any position at the location
    axes: list[AxisValue]|None = None  # None: any position in the layout

    def matches(self, position: Position) -> bool:
        if position.location_id != self.location_id:
            return False
        if self.layout_id is None:
            return True
        if position.layout_id != self.layout_id:
            return False
        coordinates = position.coordinates or []
        for axis in self.axes or []:
            if axis.index >= len(coordinates) or str(coordinates[axis.index]) != axis.value:
                return False
        return True

@dataclass
class AnalysisExclusion:
    """
    A rule excluding records from an analysis.

    A record matches when it matches ALL provided criteria;
    within a list criterion ANY element may match. Matching is exact.

    Time bounds apply to the record start/end for record criteria,
    and to the unit position history for position criteria.
    """
    record_ids: list[int]|None = None
    unit_ids: list[int]|None = None
    germplasm_ids: list[int]|None = None
    study_ids: list[int]|None = None
    positions: list[PositionExclusion]|None = None
    record_groups: list[RecordGroupMember]|None = None
    start: datetime64|None = None
    end: datetime64|None = None

    def __post_init__(self):
        if self.start is not None and self.end is not None and self.start >= self.end:
            raise ValueError(f"Exclusion start ({self.start}) must be before end ({self.end})")
        if not self.has_record_criteria and not self.positions and not self.is_time_bounded:
            raise ValueError("An exclusion rule requires at least one criterion")

    @property
    def is_time_bounded(self) -> bool:
        return self.start is not None or self.end is not None

    @property
    def has_record_criteria(self) -> bool:
        return any(
            criterion is not None for criterion in (
                self.record_ids, self.unit_ids, self.germplasm_ids, self.study_ids, self.record_groups
            )
        )

    @property
    def applies_record_time(self) -> bool:
        """
        Whether record time is matched against the time bounds.
        A rule with only position criteria matches on position history alone.
        """
        return self.is_time_bounded and (self.has_record_criteria or not self.positions)

    def matches_record_time(self, start: datetime64|None, end: datetime64|None) -> bool:
        if not self.applies_record_time:
            return True
        if start is None and end is None:
            return False
        return intervals_overlap(self.start, self.end, start, end)

    def matches_positions(self, positions: list[Position]) -> bool:
        if not self.positions:
            return True
        return any(
            criterion.matches(position) and intervals_overlap(self.start, self.end, position.start, position.end)
            for criterion in self.positions
            for position in positions
        )


@dataclass
class EstimatedMeans:
    """Estimated marginal means and their contrasts"""
    terms: list[AnalysisTermReference]
    by: list[AnalysisTermReference] = field(default_factory=list)
    contrast: EstimatedMeansContrast = EstimatedMeansContrast.PAIRWISE
    control: str|None = None
    adjustment: PValueAdjustment = PValueAdjustment.TUKEY


@dataclass
class AnalysisSpec:
    """Configuration shared by all analysis types"""
    terms: list[AnalysisTerm]
    grouping: AnalysisGrouping = field(default_factory=AnalysisGrouping)

    def get_term(self, reference: AnalysisTermReference) -> AnalysisTerm|None:
        return next((t for t in self.terms if t.reference == reference), None)

    def references(self) -> list[tuple[list[str], AnalysisTermReference]]:
        """All term references in the configuration with their input paths."""
        found = []
        for i, term in enumerate(self.terms):
            found.append((['terms', str(i), 'reference'], term.reference))
            for j, slope in enumerate(term.random_slope_terms):
                found.append((['terms', str(i), 'randomSlopeTerms', str(j)], slope))
        return found

@dataclass
class AnovaSpec(AnalysisSpec):
    response: AnalysisTermReference|None = None
    interactions: list[InteractionTerm] = field(default_factory=list)
    alpha: float = 0.05
    sum_of_squares: SumOfSquaresType = SumOfSquaresType.TYPE_III
    ddf: DdfMethod = DdfMethod.SATTERTHWAITE
    estimated_means: list[EstimatedMeans] = field(default_factory=list)

    @property
    def model_terms(self) -> list[AnalysisTerm]:
        return [t for t in self.terms if t.reference != self.response]

@dataclass
class DescriptiveSpec(AnalysisSpec):
    interactions: list[InteractionTerm] = field(default_factory=list)
    estimated_means: list[EstimatedMeans] = field(default_factory=list)

@dataclass
class CorrelationSpec(AnalysisSpec):
    method: CorrelationMethod = CorrelationMethod.PEARSON

@dataclass
class MDSClustering:
    method: ClusteringMethod
    clusters: int|None = None

@dataclass
class MDSSpec(AnalysisSpec):
    distance: DistanceMetric = DistanceMetric.EUCLIDEAN
    dimensions: int = 2
    clustering: MDSClustering|None = None

@dataclass
class OutlierSpec(AnalysisSpec):
    method: OutlierDetectionMethod = OutlierDetectionMethod.Z_SCORE


@dataclass
class AnalysisRequest:
    """An analysis as submitted"""
    analysis_type: AnalysisType
    dataset_ids: list[int]
    spec: AnalysisSpec
    name: str|None = None
    exclusions: list[AnalysisExclusion] = field(default_factory=list)


class AnalysisErrorCode(str, Enum):
    CONFIG_INVALID = "CONFIG_INVALID"
    DATASET_NOT_FOUND = "DATASET_NOT_FOUND"
    DATASET_NOT_READABLE = "DATASET_NOT_READABLE"
    CONCEPT_NOT_IN_DATASETS = "CONCEPT_NOT_IN_DATASETS"
    INCOMPATIBLE_SCALE = "INCOMPATIBLE_SCALE"
    UNIT_NOT_FOUND = "UNIT_NOT_FOUND"
    GROUPING_NOT_FOUND = "GROUPING_NOT_FOUND"
    DUPLICATE_OBSERVATION = "DUPLICATE_OBSERVATION"
    INVALID_TRANSFORMATION = "INVALID_TRANSFORMATION"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    SINGLE_LEVEL_TERM = "SINGLE_LEVEL_TERM"  # model terms
    MODEL_FAILED = "MODEL_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"

class AnalysisWarningCode(str, Enum):
    EMPTY_DATASET = "EMPTY_DATASET"
    UNUSED_DATASET = "UNUSED_DATASET"
    EXCLUDED_BY_CONFIG = "EXCLUDED_BY_CONFIG"
    UNASSIGNED_TIME = "UNASSIGNED_TIME"
    UNASSIGNED_GERMPLASM = "UNASSIGNED_GERMPLASM"
    UNASSIGNED_UNIT = "UNASSIGNED_UNIT"
    UNASSIGNED_POSITION = "UNASSIGNED_POSITION"
    UNASSIGNED_RECORD_GROUP = "UNASSIGNED_RECORD_GROUP"
    MISSING_VALUES = "MISSING_VALUES"
    DATASET_FULLY_EXCLUDED = "DATASET_FULLY_EXCLUDED"
    RECORD_GROUP_LEVEL_UNMATCHED = "RECORD_GROUP_LEVEL_UNMATCHED"
    SINGLE_LEVEL_TERM = "SINGLE_LEVEL_TERM"  # descriptive
    MODEL_NOT_CONVERGED = "MODEL_NOT_CONVERGED"

@dataclass
class AnalysisMessage:
    """An error or warning reported for an analysis"""
    code: AnalysisErrorCode|AnalysisWarningCode
    message: str
    path: list[str]|None = None
    record_ids: list[int]|None = None

    def model_dump(self) -> dict:
        return {
            'code': self.code.value,
            'message': self.message,
            'path': self.path,
            'record_ids': self.record_ids
        }


class AnalysisFailed(Exception):
    """Processing of an analysis failed with the given errors"""
    def __init__(self, errors: list[AnalysisMessage]):
        self.errors = errors
        super().__init__("; ".join(e.message for e in errors))

    @classmethod
    def single(cls, code: AnalysisErrorCode, message: str, path: list[str]|None = None, record_ids: list[int]|None = None):
        return cls([AnalysisMessage(code=code, message=message, path=path, record_ids=record_ids)])

class AnalysisConfigInvalid(AnalysisFailed):
    """The submitted analysis configuration is invalid"""
