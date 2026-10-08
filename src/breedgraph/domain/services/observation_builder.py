"""
Builds analytical observations from assigned records.

An observation is identified by the levels of all dimensions (the observation unit first).
Each term is a column of a wide frame with one row per observation.
"""
from collections import Counter
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from breedgraph.domain.model.analysis import (
    AnalysisTerm, AnalysisTermReference, AnalysisTermType, TermRepresentationType, TermAggregation,
    TermTransformation, TermEffect, AnalysisMessage, AnalysisErrorCode, AnalysisWarningCode, AnalysisFailed,
    RecordGroupMember, AnalysisSpec, AnovaSpec, MDSSpec, OutlierSpec, CorrelationSpec
)
from breedgraph.domain.model.analysis_context import AnalysisContext, AnalysisRecord, ConceptContext
from breedgraph.domain.model.ontology import ScaleType
from breedgraph.domain.services.analysis_binning import Binner, parse_datetime, parse_number
from breedgraph.domain.services.analysis_dimensions import DimensionResolver, DimensionLevel

NUMERIC_AGGREGATIONS = (TermAggregation.MEAN, TermAggregation.MEDIAN, TermAggregation.SUM)

# representations of concept terms supported by each analysis, where restricted
CONCEPT_REPRESENTATIONS = {
    MDSSpec: {TermRepresentationType.CONTINUOUS},
    OutlierSpec: {TermRepresentationType.CONTINUOUS},
    CorrelationSpec: {TermRepresentationType.CONTINUOUS, TermRepresentationType.ORDINAL},
}


def check_representation(
        spec: AnalysisSpec, term: AnalysisTerm, representation: TermRepresentationType, path: list[str]
):
    """Representations resolved from the scale must suit the analysis."""
    allowed = CONCEPT_REPRESENTATIONS.get(type(spec))
    if allowed is not None and representation not in allowed:
        raise _incompatible(
            f"Concept {term.reference.concept_id} is represented as {representation.value}, "
            f"which is not supported by this analysis",
            path + ['representation']
        )
    if isinstance(spec, AnovaSpec):
        if term.reference == spec.response and representation != TermRepresentationType.CONTINUOUS:
            raise _incompatible("The response must be represented as CONTINUOUS", path + ['representation'])
        if term.effect == TermEffect.RANDOM and representation == TermRepresentationType.CONTINUOUS:
            raise _incompatible("RANDOM terms must be categorical", path + ['representation'])


@dataclass
class ObservationColumn:
    name: str
    reference: AnalysisTermReference
    kind: TermRepresentationType
    levels: list[str] | None = None  # ordered levels of CATEGORICAL and ORDINAL columns

@dataclass
class Observation:
    group: dict  # AnalysisGroup
    record_ids: list[int]
    unit_ids: list[int]  # base units of contributing records
    exclusion: dict  # AnalysisExclusion excluding the records of the observation

@dataclass
class ObservationFrame:
    data: pd.DataFrame  # one row per observation, one column per term
    columns: list[ObservationColumn]
    observations: list[Observation]


@dataclass
class _ObservationRecords:
    levels: dict[str, DimensionLevel]
    records: dict[int, list[AnalysisRecord]] = field(default_factory=dict)  # concept ID -> records
    members: set[RecordGroupMember] = field(default_factory=set)  # record group codes of the records

    def add(self, record: AnalysisRecord, levels: dict[str, DimensionLevel]):
        self.records.setdefault(record.concept_id, []).append(record)
        # records of a shared level may have different codes
        self.members.update(level.member for level in levels.values() if level.member is not None)

    @property
    def all_records(self) -> list[AnalysisRecord]:
        return [r for records in self.records.values() for r in records]


def _incompatible(message: str, path: list[str]) -> AnalysisFailed:
    return AnalysisFailed.single(AnalysisErrorCode.INCOMPATIBLE_SCALE, message, path=path)


def resolve_representation(term: AnalysisTerm, concept: ConceptContext, path: list[str]) -> TermRepresentationType:
    """Representation of a concept term, validated against its scale."""
    scale = concept.scale_type
    requested = term.representation
    if scale == ScaleType.COMPLEX:
        raise _incompatible(f"Concept {concept.concept_id} has a complex scale, which cannot be analysed", path)

    if term.aggregation == TermAggregation.COUNT:
        if requested not in (None, TermRepresentationType.CONTINUOUS) or term.binning is not None:
            raise _incompatible("COUNT aggregation produces CONTINUOUS values", path + ['aggregation'])
        return TermRepresentationType.CONTINUOUS

    if term.binning is not None:
        if scale not in (ScaleType.NUMERICAL, ScaleType.DATE):
            raise _incompatible("Binning requires a numerical or date scale", path + ['binning'])
        if requested == TermRepresentationType.CONTINUOUS:
            raise _incompatible("Binned terms cannot be represented as CONTINUOUS", path + ['representation'])
        representation = requested or TermRepresentationType.ORDINAL
    else:
        default = {
            ScaleType.NUMERICAL: TermRepresentationType.CONTINUOUS,
            ScaleType.ORDINAL: TermRepresentationType.ORDINAL
        }.get(scale, TermRepresentationType.CATEGORICAL)
        representation = requested or default
        if representation == TermRepresentationType.CONTINUOUS and scale != ScaleType.NUMERICAL:
            raise _incompatible(
                f"Concept {concept.concept_id} has a {scale.name.lower()} scale, "
                f"which cannot be represented as CONTINUOUS",
                path + ['representation']
            )

    if term.aggregation in NUMERIC_AGGREGATIONS and scale != ScaleType.NUMERICAL:
        raise _incompatible(f"{term.aggregation.value} aggregation requires a numerical scale", path + ['aggregation'])
    if term.aggregation in (TermAggregation.MIN, TermAggregation.MAX) and not (
            scale in (ScaleType.NUMERICAL, ScaleType.DATE) or representation == TermRepresentationType.ORDINAL
    ):
        raise _incompatible(
            f"{term.aggregation.value} aggregation requires ordered values", path + ['aggregation']
        )
    return representation


class ObservationBuilder:

    def __init__(self, context: AnalysisContext, resolvers: list[DimensionResolver]):
        self.context = context
        self.resolvers = resolvers
        self.spec_path = [context.request.analysis_type.input_field]
        self._observations: dict[tuple[str, ...], _ObservationRecords] = {}

    def add(self, record: AnalysisRecord, levels: dict[str, DimensionLevel]):
        key = tuple(levels[r.name].key for r in self.resolvers)
        if key not in self._observations:
            self._observations[key] = _ObservationRecords(levels=levels)
        self._observations[key].add(record, levels)

    def build(self, warnings: list[AnalysisMessage]) -> ObservationFrame:
        observations = list(self._observations.values())
        if not observations:
            raise AnalysisFailed.single(
                AnalysisErrorCode.INSUFFICIENT_DATA, "No records remain after exclusions and dimension assignment"
            )

        data = {}
        columns = []
        for i, term in enumerate(self.context.request.spec.terms):
            path = self.spec_path + ['terms', str(i)]
            if term.reference.type == AnalysisTermType.CONCEPT:
                column, values = self._concept_column(term, observations, path, warnings)
            else:
                column, values = self._domain_column(term, observations)
            columns.append(column)
            data[column.name] = values

        frame = pd.DataFrame(data, columns=[c.name for c in columns])
        return ObservationFrame(
            data=frame,
            columns=columns,
            observations=[self._observation(o) for o in observations]
        )

    """ Concept terms """
    def _concept_column(
            self,
            term: AnalysisTerm,
            observations: list[_ObservationRecords],
            path: list[str],
            warnings: list[AnalysisMessage]
    ) -> tuple[ObservationColumn, pd.Series]:
        concept = self.context.concepts[term.reference.concept_id]
        representation = resolve_representation(term, concept, path)
        check_representation(self.context.request.spec, term, representation, path)

        duplicates = [
            r.record_id for o in observations
            for records in [o.records.get(concept.concept_id, [])] if len(records) > 1
            for r in records
        ]
        if duplicates and term.aggregation == TermAggregation.NONE:
            raise AnalysisFailed.single(
                AnalysisErrorCode.DUPLICATE_OBSERVATION,
                f"Concept {concept.concept_id} has more than one value for some observations; "
                f"configure an aggregation or additional dimensions",
                path=path + ['aggregation'],
                record_ids=sorted(duplicates)
            )

        parse = self._parser(concept, term)
        values = []
        for o in observations:
            raw = [parse(r.value) for r in o.records.get(concept.concept_id, []) if r.value is not None]
            values.append(self._aggregate(term, raw, concept))

        binner = None
        if term.binning is not None:
            try:
                binner = Binner(term.binning, parse_datetime if concept.scale_type == ScaleType.DATE else parse_number)
            except ValueError as e:
                raise AnalysisFailed.single(AnalysisErrorCode.CONFIG_INVALID, str(e), path=path + ['binning', 'boundaries'])
            values = [binner.bin(v).label if v is not None else None for v in values]

        column = ObservationColumn(name=term.reference.label, reference=term.reference, kind=representation)
        if representation == TermRepresentationType.CONTINUOUS:
            series = pd.Series([v if v is not None else np.nan for v in values], dtype=float)
            series = self._transform(term, series, observations, path)
            missing_levels = 0
        else:
            column.levels = term.level_order or (binner.labels if binner else None) or (
                concept.categories if representation == TermRepresentationType.ORDINAL else None
            ) or sorted({str(v) for v in values if v is not None})
            known = set(column.levels)
            missing_levels = sum(1 for v in values if v is not None and str(v) not in known)
            series = pd.Series([str(v) if v is not None and str(v) in known else None for v in values], dtype=object)

        missing = int(series.isna().sum())
        if missing:
            message = f"{missing} of {len(series)} observations have no value for concept {concept.concept_id}"
            if missing_levels:
                message += f", including {missing_levels} with values not in the level order"
            warnings.append(AnalysisMessage(code=AnalysisWarningCode.MISSING_VALUES, message=message, path=path))
        return column, series

    @staticmethod
    def _parser(concept: ConceptContext, term: AnalysisTerm):
        if term.aggregation == TermAggregation.COUNT:
            return lambda value: value
        if concept.scale_type == ScaleType.NUMERICAL:
            return parse_number
        if concept.scale_type == ScaleType.DATE and (
                term.binning is not None or term.aggregation in (TermAggregation.MIN, TermAggregation.MAX)
        ):
            return parse_datetime
        return str

    @staticmethod
    def _aggregate(term: AnalysisTerm, values: list, concept: ConceptContext):
        aggregation = term.aggregation
        if aggregation == TermAggregation.COUNT:
            return len(values)
        if not values:
            return None
        if aggregation == TermAggregation.NONE:
            return values[0]
        if aggregation == TermAggregation.MEAN:
            return float(np.mean(values))
        if aggregation == TermAggregation.MEDIAN:
            return float(np.median(values))
        if aggregation == TermAggregation.SUM:
            return float(np.sum(values))

        order = term.level_order or concept.categories
        if order is not None and isinstance(values[0], str):
            # ordinal values are ordered by level, values not in the order are ignored
            rank = {level: i for i, level in enumerate(order)}
            values = [v for v in values if v in rank]
            if not values:
                return None
            sort_key = rank.__getitem__
        else:
            sort_key = None

        if aggregation == TermAggregation.MIN:
            return min(values, key=sort_key)
        if aggregation == TermAggregation.MAX:
            return max(values, key=sort_key)
        if aggregation == TermAggregation.MODE:
            counts = Counter(values)
            top = max(counts.values())
            # ties resolve to the lowest value
            return min((v for v, c in counts.items() if c == top), key=sort_key)
        raise ValueError(f"Unsupported aggregation {aggregation}")

    def _transform(
            self,
            term: AnalysisTerm,
            series: pd.Series,
            observations: list[_ObservationRecords],
            path: list[str]
    ) -> pd.Series:
        domains = {
            TermTransformation.LOG: (lambda s: s > 0, "positive values"),
            TermTransformation.LOG1P: (lambda s: s > -1, "values greater than -1"),
            TermTransformation.SQRT: (lambda s: s >= 0, "non-negative values"),
            TermTransformation.RECIPROCAL: (lambda s: s != 0, "non-zero values"),
        }
        for j, transformation in enumerate(term.transformations):
            transformation_path = path + ['transformations', str(j)]
            if transformation in domains:
                valid, description = domains[transformation]
                invalid = series.notna() & ~valid(series)
                if invalid.any():
                    raise AnalysisFailed.single(
                        AnalysisErrorCode.INVALID_TRANSFORMATION,
                        f"{transformation.value} requires {description}; {int(invalid.sum())} observations are invalid",
                        path=transformation_path,
                        record_ids=sorted(
                            r.record_id for i in np.flatnonzero(invalid.to_numpy())
                            for r in observations[i].records.get(term.reference.concept_id, [])
                        )
                    )
            if transformation == TermTransformation.CENTER:
                series = series - series.mean()
            elif transformation == TermTransformation.STANDARDIZE:
                sd = series.std(ddof=1)
                if not np.isfinite(sd) or sd == 0:
                    raise AnalysisFailed.single(
                        AnalysisErrorCode.INVALID_TRANSFORMATION,
                        "STANDARDIZE requires at least two distinct values",
                        path=transformation_path
                    )
                series = (series - series.mean()) / sd
            elif transformation == TermTransformation.LOG:
                series = np.log(series)
            elif transformation == TermTransformation.LOG1P:
                series = np.log1p(series)
            elif transformation == TermTransformation.SQRT:
                series = np.sqrt(series)
            elif transformation == TermTransformation.RECIPROCAL:
                series = 1 / series
        return series

    """ Domain terms """
    def _domain_column(
            self,
            term: AnalysisTerm,
            observations: list[_ObservationRecords]
    ) -> tuple[ObservationColumn, pd.Series]:
        name = term.reference.label
        values = [o.levels[name].key for o in observations]
        if term.reference.type == AnalysisTermType.TIME:
            default = TermRepresentationType.ORDINAL
            levels = [label for label in self.context.request.spec.grouping.time.binning.labels if label in set(values)]
        else:
            default = TermRepresentationType.CATEGORICAL
            levels = sorted(set(values))
        if term.level_order:
            levels = list(term.level_order) + [level for level in levels if level not in term.level_order]
        column = ObservationColumn(
            name=name, reference=term.reference, kind=term.representation or default, levels=levels
        )
        return column, pd.Series(values, dtype=object)

    """ Observation metadata """
    def _observation(self, observation: _ObservationRecords) -> Observation:
        group = {
            'time': None, 'germplasm_id': None, 'unit_id': None, 'position': None, 'study_id': None,
            'record_groups': []
        }
        exclusion_start = exclusion_end = None
        for resolver in self.resolvers:
            level = observation.levels[resolver.name]
            term_type = resolver.reference.type
            if term_type == AnalysisTermType.UNIT:
                group['unit_id'] = level.output
            elif term_type == AnalysisTermType.TIME:
                group['time'] = level.output
                exclusion_start, exclusion_end = level.start, level.end
            elif term_type == AnalysisTermType.GERMPLASM:
                group['germplasm_id'] = level.output
            elif term_type == AnalysisTermType.POSITION:
                group['position'] = level.output
            elif term_type == AnalysisTermType.STUDY:
                group['study_id'] = level.output
            elif term_type == AnalysisTermType.RECORD_GROUP:
                group['record_groups'].append(level.output)

        records = observation.all_records
        unit_ids = sorted({r.unit_id for r in records if r.unit_id is not None})
        exclusion = {
            'unit_ids': unit_ids,
            'start': str(exclusion_start) if exclusion_start is not None else None,
            'end': str(exclusion_end) if exclusion_end is not None else None,
            'record_groups': [
                {'grouping_id': m.grouping_id, 'code': m.code, 'dataset_id': m.dataset_id}
                for m in sorted(observation.members, key=lambda m: (m.grouping_id, m.code, m.dataset_id or 0))
            ] or None
        }
        return Observation(
            group=group,
            record_ids=sorted(r.record_id for r in records),
            unit_ids=unit_ids,
            exclusion=exclusion
        )
