"""
Importers for analysis submissions.

The stored analysis input is an exact mirror of the GraphQL AnalysisInput
(with snake_case keys). These models validate it and convert it to the domain
AnalysisRequest. Domain invariants are checked by building the domain object
in a model validator, so their errors are reported with the field path.
"""
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from breedgraph.domain.model.time_descriptors import PyDT64
from breedgraph.domain.model.blocks import Position
from breedgraph.domain.model.analysis import (
    AnalysisType, AnalysisTermType, TermRepresentationType, TermTransformation, TermAggregation, TermEffect,
    TimeAssignment, BinningBoundary, DistanceMetric, CorrelationMethod, OutlierDetectionMethod, ClusteringMethod,
    SumOfSquaresType, DdfMethod, EstimatedMeansContrast, PValueAdjustment,
    AnalysisTermReference, Binning, AnalysisTerm, InteractionTerm,
    TimeSpecification, GermplasmGrouping, UnitGrouping, PositionGrouping, AnalysisGrouping,
    RecordGroupMember, RecordGroupLevel, RecordGroupDimension,
    AxisValue, PositionExclusion, AnalysisExclusion,
    EstimatedMeans, AnovaSpec, DescriptiveSpec, CorrelationSpec, MDSClustering, MDSSpec, OutlierSpec,
    AnalysisRequest, AnalysisMessage, AnalysisErrorCode
)


class ImportModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

    def to_domain(self):
        raise NotImplementedError

class DomainCheckedModel(ImportModel):
    """Builds the domain object on validation, so domain invariants are reported with the field path."""
    @model_validator(mode='after')
    def _check_domain(self):
        self.to_domain()
        return self


""" Terms """
class AnalysisTermReferenceImport(DomainCheckedModel):
    type: AnalysisTermType
    concept_id: int | None = None
    record_group_dimension: str | None = None

    def to_domain(self) -> AnalysisTermReference:
        return AnalysisTermReference(
            type=self.type,
            concept_id=self.concept_id,
            record_group_dimension=self.record_group_dimension
        )

class BinningImport(DomainCheckedModel):
    boundaries: list[str]
    labels: list[str]
    boundary: BinningBoundary

    def to_domain(self) -> Binning:
        return Binning(boundaries=self.boundaries, labels=self.labels, boundary=self.boundary)

class AnalysisTermImport(ImportModel):
    reference: AnalysisTermReferenceImport
    representation: TermRepresentationType | None = None
    binning: BinningImport | None = None
    level_order: list[str] | None = None
    transformations: list[TermTransformation] | None = None
    aggregation: TermAggregation | None = None
    effect: TermEffect | None = None
    random_slope_terms: list[AnalysisTermReferenceImport] | None = None

    def to_domain(self) -> AnalysisTerm:
        return AnalysisTerm(
            reference=self.reference.to_domain(),
            representation=self.representation,
            binning=self.binning.to_domain() if self.binning else None,
            level_order=self.level_order,
            transformations=list(self.transformations or []),
            aggregation=self.aggregation or TermAggregation.NONE,
            effect=self.effect,
            random_slope_terms=[t.to_domain() for t in self.random_slope_terms or []]
        )

class InteractionTermImport(ImportModel):
    terms: list[AnalysisTermReferenceImport] = Field(min_length=2)

    def to_domain(self) -> InteractionTerm:
        return InteractionTerm(terms=[t.to_domain() for t in self.terms])


""" Grouping """
class TimeSpecificationImport(ImportModel):
    assignment: TimeAssignment
    binning: BinningImport

    def to_domain(self) -> TimeSpecification:
        return TimeSpecification(assignment=self.assignment, binning=self.binning.to_domain())

class GermplasmGroupingImport(ImportModel):
    germplasm_ids: list[int] = Field(min_length=1)

    def to_domain(self) -> GermplasmGrouping:
        return GermplasmGrouping(germplasm_ids=self.germplasm_ids)

class UnitGroupingImport(ImportModel):
    unit_ids: list[int] = Field(min_length=1)

    def to_domain(self) -> UnitGrouping:
        return UnitGrouping(unit_ids=self.unit_ids)

class PositionImport(ImportModel):
    location_id: int
    layout_id: int | None = None
    coordinates: list[str | None] | None = None
    start: PyDT64 | None = None
    end: PyDT64 | None = None

    def to_domain(self) -> Position:
        return Position(
            location_id=self.location_id,
            layout_id=self.layout_id,
            coordinates=self.coordinates,
            start=self.start,
            end=self.end
        )

class PositionGroupingImport(ImportModel):
    location_id: int
    layout_id: int | None = None
    axis_indexes: list[int] | None = None
    positions: list[PositionImport] | None = None
    time: PyDT64 | None = None

    def to_domain(self) -> PositionGrouping:
        return PositionGrouping(
            location_id=self.location_id,
            layout_id=self.layout_id,
            axis_indexes=self.axis_indexes,
            positions=[p.to_domain() for p in self.positions] if self.positions is not None else None,
            time=self.time
        )

class RecordGroupMemberImport(DomainCheckedModel):
    grouping_id: int
    code: str
    dataset_id: int | None = None

    def to_domain(self) -> RecordGroupMember:
        return RecordGroupMember(grouping_id=self.grouping_id, code=self.code, dataset_id=self.dataset_id)

class RecordGroupLevelImport(DomainCheckedModel):
    label: str
    members: list[RecordGroupMemberImport]

    def to_domain(self) -> RecordGroupLevel:
        return RecordGroupLevel(label=self.label, members=[m.to_domain() for m in self.members])

class RecordGroupDimensionImport(DomainCheckedModel):
    name: str
    grouping_ids: list[int]
    levels: list[RecordGroupLevelImport] | None = None

    def to_domain(self) -> RecordGroupDimension:
        return RecordGroupDimension(
            name=self.name,
            grouping_ids=self.grouping_ids,
            levels=[l.to_domain() for l in self.levels or []]
        )

class AnalysisGroupingImport(ImportModel):
    time: TimeSpecificationImport | None = None
    germplasm: GermplasmGroupingImport | None = None
    unit: UnitGroupingImport | None = None
    position: PositionGroupingImport | None = None
    record_groups: list[RecordGroupDimensionImport] | None = None

    def to_domain(self) -> AnalysisGrouping:
        return AnalysisGrouping(
            time=self.time.to_domain() if self.time else None,
            germplasm=self.germplasm.to_domain() if self.germplasm else None,
            unit=self.unit.to_domain() if self.unit else None,
            position=self.position.to_domain() if self.position else None,
            record_groups=[d.to_domain() for d in self.record_groups or []]
        )


""" Exclusions """
class AxisValueImport(ImportModel):
    index: int = Field(ge=0)
    value: str

    def to_domain(self) -> AxisValue:
        return AxisValue(index=self.index, value=self.value)

class PositionExclusionImport(ImportModel):
    location_id: int
    layout_id: int | None = None
    axes: list[AxisValueImport] | None = None

    @model_validator(mode='after')
    def _axes_require_layout(self):
        if self.axes is not None and self.layout_id is None:
            raise ValueError("A layout is required to match axes")
        return self

    def to_domain(self) -> PositionExclusion:
        return PositionExclusion(
            location_id=self.location_id,
            layout_id=self.layout_id,
            axes=[a.to_domain() for a in self.axes] if self.axes is not None else None
        )

class AnalysisExclusionImport(DomainCheckedModel):
    record_ids: list[int] | None = None
    unit_ids: list[int] | None = None
    germplasm_ids: list[int] | None = None
    study_ids: list[int] | None = None
    positions: list[PositionExclusionImport] | None = None
    record_groups: list[RecordGroupMemberImport] | None = None
    start: PyDT64 | None = None
    end: PyDT64 | None = None

    def to_domain(self) -> AnalysisExclusion:
        return AnalysisExclusion(
            record_ids=self.record_ids,
            unit_ids=self.unit_ids,
            germplasm_ids=self.germplasm_ids,
            study_ids=self.study_ids,
            positions=[p.to_domain() for p in self.positions] if self.positions is not None else None,
            record_groups=[m.to_domain() for m in self.record_groups] if self.record_groups is not None else None,
            start=self.start,
            end=self.end
        )


""" Analysis specific configuration """
class EstimatedMeansImport(ImportModel):
    terms: list[AnalysisTermReferenceImport] = Field(min_length=1)
    by: list[AnalysisTermReferenceImport] | None = None
    contrast: EstimatedMeansContrast | None = None
    control: str | None = None
    adjustment: PValueAdjustment | None = None

    def to_domain(self) -> EstimatedMeans:
        return EstimatedMeans(
            terms=[t.to_domain() for t in self.terms],
            by=[t.to_domain() for t in self.by or []],
            contrast=self.contrast or EstimatedMeansContrast.PAIRWISE,
            control=self.control,
            adjustment=self.adjustment or PValueAdjustment.TUKEY
        )

class AnalysisSpecImport(ImportModel):
    terms: list[AnalysisTermImport] = Field(min_length=1)
    grouping: AnalysisGroupingImport | None = None

    def _shared(self) -> dict:
        return {
            'terms': [t.to_domain() for t in self.terms],
            'grouping': self.grouping.to_domain() if self.grouping else AnalysisGrouping()
        }

class AnovaImport(AnalysisSpecImport):
    response: AnalysisTermReferenceImport
    interactions: list[InteractionTermImport] | None = None
    alpha: float | None = Field(default=None, gt=0, lt=1)
    sum_of_squares: SumOfSquaresType | None = None
    ddf: DdfMethod | None = None
    estimated_means: list[EstimatedMeansImport] | None = None

    def to_domain(self) -> AnovaSpec:
        return AnovaSpec(
            **self._shared(),
            response=self.response.to_domain(),
            interactions=[i.to_domain() for i in self.interactions or []],
            alpha=self.alpha if self.alpha is not None else 0.05,
            sum_of_squares=self.sum_of_squares or SumOfSquaresType.TYPE_III,
            ddf=self.ddf or DdfMethod.SATTERTHWAITE,
            estimated_means=[e.to_domain() for e in self.estimated_means or []]
        )

class DescriptiveStatisticsImport(AnalysisSpecImport):
    interactions: list[InteractionTermImport] | None = None
    estimated_means: list[EstimatedMeansImport] | None = None

    def to_domain(self) -> DescriptiveSpec:
        return DescriptiveSpec(
            **self._shared(),
            interactions=[i.to_domain() for i in self.interactions or []],
            estimated_means=[e.to_domain() for e in self.estimated_means or []]
        )

class CorrelationImport(AnalysisSpecImport):
    method: CorrelationMethod

    def to_domain(self) -> CorrelationSpec:
        return CorrelationSpec(**self._shared(), method=self.method)

class MDSClusteringImport(ImportModel):
    method: ClusteringMethod
    clusters: int | None = Field(default=None, ge=1)

    def to_domain(self) -> MDSClustering:
        return MDSClustering(method=self.method, clusters=self.clusters)

class MDSImport(AnalysisSpecImport):
    distance: DistanceMetric
    dimensions: int | None = Field(default=None, ge=1)
    clustering: MDSClusteringImport | None = None

    def to_domain(self) -> MDSSpec:
        return MDSSpec(
            **self._shared(),
            distance=self.distance,
            dimensions=self.dimensions if self.dimensions is not None else 2,
            clustering=self.clustering.to_domain() if self.clustering else None
        )

class OutlierDetectionImport(AnalysisSpecImport):
    method: OutlierDetectionMethod

    def to_domain(self) -> OutlierSpec:
        return OutlierSpec(**self._shared(), method=self.method)


class AnalysisInputImport(ImportModel):
    analysis_type: AnalysisType
    name: str | None = None
    dataset_ids: list[int] = Field(min_length=1)
    exclusions: list[AnalysisExclusionImport] | None = None

    anova: AnovaImport | None = None
    mds: MDSImport | None = None
    correlation: CorrelationImport | None = None
    descriptive_statistics: DescriptiveStatisticsImport | None = None
    outlier_detection: OutlierDetectionImport | None = None

    @model_validator(mode='after')
    def _single_matching_spec(self):
        provided = [t for t in AnalysisType if getattr(self, t.input_key) is not None]
        if provided != [self.analysis_type]:
            raise ValueError(
                f"Exactly one analysis configuration is required, "
                f"matching analysisType: {self.analysis_type.input_field}"
            )
        return self

    @property
    def spec(self) -> AnalysisSpecImport:
        return getattr(self, self.analysis_type.input_key)

    def to_domain(self) -> AnalysisRequest:
        return AnalysisRequest(
            analysis_type=self.analysis_type,
            name=self.name,
            dataset_ids=self.dataset_ids,
            exclusions=[e.to_domain() for e in self.exclusions or []],
            spec=self.spec.to_domain()
        )


def _camel(name: str) -> str:
    head, *tail = name.split('_')
    return head + ''.join(part.title() for part in tail)

def validation_messages(error: ValidationError) -> list[AnalysisMessage]:
    """Map pydantic validation errors to CONFIG_INVALID messages with camelCase input paths."""
    messages = []
    for e in error.errors():
        # union members and validator names are not part of the input path
        path = [str(p) if isinstance(p, int) else _camel(p) for p in e['loc'] if not str(p).startswith('function-')]
        message = e['msg'].removeprefix('Value error, ')
        messages.append(AnalysisMessage(code=AnalysisErrorCode.CONFIG_INVALID, message=message, path=path or None))
    return messages
