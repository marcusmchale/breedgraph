"""
Builds analytical observations from assigned records.

An observation is identified by the levels of all dimensions (the observation unit first).
Each term is a column of a wide frame with one row per observation.

When an analysis has variable terms, variable records form the observations, and factor records describe them
(attach_context): a factor record applies to an observation of its own unit, a unit rolled up into it, or failing
those of the nearest units above with a record of that factor, one on each lineage, which must agree
(domain.services.lineages), in its time bin (or every bin when it has no time) and its record group levels (or every
level when it has no code).
"""
from collections import Counter
from dataclasses import dataclass, field

import numpy as np
from numpy import timedelta64
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
from breedgraph.domain.services.lineages import nearest_on_each_lineage

NUMERIC_AGGREGATIONS = (TermAggregation.MEAN, TermAggregation.MEDIAN, TermAggregation.SUM)
# aggregations giving the same result whether or not replicates are combined first (or that count records)
UNWEIGHTED_AGGREGATIONS = (TermAggregation.NONE, TermAggregation.MIN, TermAggregation.MAX, TermAggregation.COUNT)

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
    unit_ids: list[int]  # base units of the records forming the observation, not the factor records describing it
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

    context_ids: set[int] = field(default_factory=set)  # factor records describing the observation

    def add(self, record: AnalysisRecord, levels: dict[str, DimensionLevel]):
        self.records.setdefault(record.concept_id, []).append(record)
        # records of a shared level may have different codes
        self.members.update(level.member for level in levels.values() if level.member is not None)

    def add_context(self, record: AnalysisRecord):
        self.records.setdefault(record.concept_id, []).append(record)
        self.context_ids.add(record.record_id)

    @property
    def all_records(self) -> list[AnalysisRecord]:
        return [r for records in self.records.values() for r in records]

    @property
    def own_records(self) -> list[AnalysisRecord]:
        """The records that form the observation, not those describing it"""
        return [r for r in self.all_records if r.record_id not in self.context_ids]


@dataclass
class _ContextRecord:
    record: AnalysisRecord
    levels: dict[str, DimensionLevel | None]  # None: applies across the dimension


def _split_by_window(records: list[AnalysisRecord], window: timedelta64) -> list[list[AnalysisRecord]]:
    """
    Replicates as readings: each reading starts at its first record (by start, or end without a start)
    and takes the records up to window later. Records without a time are one reading.
    """
    time = lambda r: r.start if r.start is not None else r.end
    untimed = [r for r in records if time(r) is None]
    readings = [untimed] if untimed else []
    anchor = None
    for record in sorted((r for r in records if time(r) is not None), key=lambda r: (time(r), r.record_id)):
        if anchor is None or time(record) - anchor > window:
            anchor = time(record)
            readings.append([])
        readings[-1].append(record)
    return readings


def _axis_level_order(key: str) -> tuple:
    """A layout axis level, layoutId|value, ordered by layout and then by value, numbers before text"""
    layout_id, _, value = key.partition('|')
    try:
        number = parse_number(value)
    except ValueError:
        number = None
    if number is None or not np.isfinite(number):
        return int(layout_id), True, 0.0, value
    return int(layout_id), False, number, value


def _number_level(value) -> str:
    """A number as a level, written as it would be recorded: 120 for 120.0, 0.5 for 0.5"""
    number = float(value)
    return str(int(number)) if number.is_integer() else repr(number)


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

    replicate_aggregation = term.replicate_aggregation.aggregation if term.replicate_aggregation else None
    for aggregation, field_name in (
            (term.aggregation, ['aggregation']), (replicate_aggregation, ['replicateAggregation', 'aggregation'])
    ):
        if aggregation in NUMERIC_AGGREGATIONS and scale != ScaleType.NUMERICAL:
            raise _incompatible(f"{aggregation.value} aggregation requires a numerical scale", path + field_name)
        if aggregation in (TermAggregation.MIN, TermAggregation.MAX) and not (
                scale in (ScaleType.NUMERICAL, ScaleType.DATE) or representation == TermRepresentationType.ORDINAL
        ):
            raise _incompatible(f"{aggregation.value} aggregation requires ordered values", path + field_name)
    return representation


class ObservationBuilder:

    def __init__(self, context: AnalysisContext, resolvers: list[DimensionResolver]):
        self.context = context
        self.resolvers = resolvers
        self.spec_path = [context.request.analysis_type.input_field]
        self._observations: dict[tuple[str, ...], _ObservationRecords] = {}
        self._context: list[_ContextRecord] = []
        self._differing: set[int] = set()  # factor records whose lineages differ, describing no observation for it

    def add(self, record: AnalysisRecord, levels: dict[str, DimensionLevel]):
        key = tuple(levels[r.name].key for r in self.resolvers)
        if key not in self._observations:
            self._observations[key] = _ObservationRecords(levels=levels)
        self._observations[key].add(record, levels)

    def add_context(self, record: AnalysisRecord, levels: dict[str, DimensionLevel | None]):
        """A factor record, attached to the observations it describes by attach_context"""
        self._context.append(_ContextRecord(record, levels))

    def attach_context(self) -> set[int]:
        """
        Adds each factor record to the observations it describes. For each observation and factor, the records of
        the closest units apply: the observation's unit (or one rolled up into it), else the nearest units above it
        with any, one on each lineage, when they agree; where they differ, none applies (context_warnings).
        Returns the IDs of the factor records that describe an observation.
        """
        if not self._context:
            return set()
        unit_name = self.resolvers[0].name
        by_unit: dict[str, list[_ContextRecord]] = {}  # the observation unit a record rolls up to
        by_base: dict[int, list[_ContextRecord]] = {}  # the record's own unit
        for entry in self._context:
            unit_level = entry.levels[unit_name]
            if unit_level is not None:
                by_unit.setdefault(unit_level.key, []).append(entry)
            by_base.setdefault(entry.record.unit_id, []).append(entry)
        concepts = {entry.record.concept_id for entry in self._context}

        def parents_of(unit_id: int) -> list[int]:
            unit = self.context.units.get(unit_id)
            return unit.parent_ids if unit is not None else []

        attached = set()
        for observation in self._observations.values():
            unit_level = observation.levels[unit_name]
            own = [entry for entry in by_unit.get(unit_level.key, []) if self._describes(entry, observation, unit_name)]
            for entry in own:
                observation.add_context(entry.record)
                attached.add(entry.record.record_id)
            unit = self.context.units.get(unit_level.output)
            if unit is None:
                continue
            for concept_id in concepts - {entry.record.concept_id for entry in own}:
                def describing(unit_id: int) -> list[_ContextRecord]:
                    return [
                        entry for entry in by_base.get(unit_id, [])
                        if entry.record.concept_id == concept_id and self._describes(entry, observation, unit_name)
                    ]
                sources = nearest_on_each_lineage(unit.unit_id, parents_of, lambda u: bool(describing(u)))
                if not sources:
                    continue
                found = {source: describing(source) for source in sources}
                if len({tuple(sorted({str(e.record.value) for e in entries})) for entries in found.values()}) > 1:
                    self._differing.update(e.record.record_id for entries in found.values() for e in entries)
                    continue
                for entry in found[sources[0]]:
                    observation.add_context(entry.record)
                    attached.add(entry.record.record_id)
        return attached

    def context_warnings(self) -> list[AnalysisMessage]:
        """Where factor records on separate lineages above an observation's unit differ, so describe it not at all"""
        if not self._differing:
            return []
        return [AnalysisMessage(
            code=AnalysisWarningCode.FACTOR_LINEAGES_DIFFER,
            message=(
                f"{len(self._differing)} factor records differ between separate lineages above some units, e.g. a sample "
                f"pooled from trees given different treatments, so they describe none of those units' observations"
            ),
            record_ids=sorted(self._differing)
        )]

    def _describes(self, entry: _ContextRecord, observation: _ObservationRecords, unit_name: str) -> bool:
        return all(
            level is None or level.key == observation.levels[name].key
            for name, level in entry.levels.items() if name != unit_name
        )

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

        # the records of each observation, as readings: replicates of WITHIN_UNIT groupings together
        window = term.replicate_aggregation.span if term.replicate_aggregation else None
        readings = [self._readings(o.records.get(concept.concept_id, []), window) for o in observations]
        replicate_aggregation = term.replicate_aggregation.aggregation if term.replicate_aggregation else None

        duplicates = []
        only_replicates = True  # whether every duplicate is a replicate of a single reading
        pooled = False  # whether replicates are pooled by the term's aggregation
        for groups in readings:
            values_count = len(groups) if replicate_aggregation else sum(len(g) for g in groups)
            if values_count > 1:
                duplicates += [r.record_id for g in groups for r in g]
                if len(groups) > 1:
                    only_replicates = False
            if replicate_aggregation is None and any(len(g) > 1 for g in groups):
                pooled = True

        if duplicates and term.aggregation == TermAggregation.NONE:
            if only_replicates and replicate_aggregation is None:
                raise AnalysisFailed.single(
                    AnalysisErrorCode.DUPLICATE_OBSERVATION,
                    f"Concept {concept.concept_id} has replicates (codes of WITHIN_UNIT groupings) for some observations; "
                    f"configure a replicate aggregation, or a record group dimension to keep each replicate",
                    path=path + ['replicateAggregation'],
                    record_ids=sorted(duplicates)
                )
            raise AnalysisFailed.single(
                AnalysisErrorCode.DUPLICATE_OBSERVATION,
                f"Concept {concept.concept_id} has more than one value for some observations; "
                f"configure an aggregation or additional dimensions",
                path=path + ['aggregation'],
                record_ids=sorted(duplicates)
            )
        if pooled and term.aggregation not in UNWEIGHTED_AGGREGATIONS:
            warnings.append(AnalysisMessage(
                code=AnalysisWarningCode.REPLICATES_POOLED,
                message=(
                    f"Replicates of concept {concept.concept_id} are pooled by the {term.aggregation.value} aggregation, "
                    f"so units and times with more replicates weigh more; configure a replicate aggregation "
                    f"to combine the replicates of each reading first"
                ),
                path=path + ['replicateAggregation']
            ))

        parse = self._parser(concept, term)
        values = []
        for groups in readings:
            if replicate_aggregation is None:
                raw = [parse(r.value) for g in groups for r in g if r.value is not None]
            else:
                raw = [
                    self._aggregate(replicate_aggregation, [parse(r.value) for r in g if r.value is not None], term, concept)
                    for g in groups
                ]
                raw = [v for v in raw if v is not None]
            values.append(self._aggregate(term.aggregation, raw, term, concept))

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
            if concept.scale_type == ScaleType.NUMERICAL and binner is None:
                # numbers as levels: each written as recorded, not as the float parsed, in numeric order
                values = [_number_level(v) if v is not None else None for v in values]
                found = sorted({v for v in values if v is not None}, key=float)
            else:
                found = sorted({str(v) for v in values if v is not None})
            column.levels = term.level_order or (binner.labels if binner else None) or (
                concept.categories if representation == TermRepresentationType.ORDINAL else None
            ) or found
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

    def _readings(self, records: list[AnalysisRecord], window: timedelta64 | None) -> list[list[AnalysisRecord]]:
        """
        Records grouped by reading, any record without codes of WITHIN_UNIT groupings alone.
        Replicates (same base unit, WITHIN_UNIT groupings and scopes) are one reading if they have the same
        start and end, or with a window, if they are within the window of the reading's first record.
        """
        keyed: dict[tuple, list[AnalysisRecord]] = {}
        for i, record in enumerate(records):
            key = self.context.replicate_key(record)
            if key is None:
                key = ('record', i)
            elif window is None:
                key = ('replicates', key, record.start, record.end)
            else:
                key = ('replicates', key)
            keyed.setdefault(key, []).append(record)
        if window is None:
            return list(keyed.values())
        return [
            reading for key, group in keyed.items()
            for reading in ([group] if key[0] == 'record' else _split_by_window(group, window))
        ]

    @staticmethod
    def _parser(concept: ConceptContext, term: AnalysisTerm):
        if term.aggregation == TermAggregation.COUNT:
            return lambda value: value
        if concept.scale_type == ScaleType.NUMERICAL:
            return parse_number
        ordered = (TermAggregation.MIN, TermAggregation.MAX)
        if concept.scale_type == ScaleType.DATE and (
                term.binning is not None or term.aggregation in ordered
                or (term.replicate_aggregation is not None and term.replicate_aggregation.aggregation in ordered)
        ):
            return parse_datetime
        return str

    @staticmethod
    def _aggregate(aggregation: TermAggregation, values: list, term: AnalysisTerm, concept: ConceptContext):
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
        elif term.reference.type == AnalysisTermType.LAYOUT_AXIS:
            # by layout, then the values in numeric order where they are numbers, e.g. rows 2 before 10
            default = TermRepresentationType.CATEGORICAL
            levels = sorted(set(values), key=_axis_level_order)
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
            'time': None, 'germplasm_id': None, 'unit_id': None, 'location_id': None, 'study_id': None,
            'record_groups': [], 'layout_axes': []
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
            elif term_type == AnalysisTermType.LOCATION:
                group['location_id'] = level.output
            elif term_type == AnalysisTermType.LAYOUT_AXIS:
                group['layout_axes'].append(level.output)
            elif term_type == AnalysisTermType.STUDY:
                group['study_id'] = level.output
            elif term_type == AnalysisTermType.RECORD_GROUP:
                group['record_groups'].append(level.output)

        records = observation.all_records
        # the exclusion rule matches the observation's own records, not the factor records describing it
        unit_ids = sorted({r.unit_id for r in observation.own_records if r.unit_id is not None})
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
