"""
Resolvers assigning records to the levels of the dimensions of analytical observation identity.

A record that cannot be assigned to a configured dimension is excluded from the analysis,
and reported in one warning per dimension.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from numpy import datetime64, timedelta64

from breedgraph.domain.model.analysis import (
    AnalysisTermType, AnalysisTermReference, AnalysisMessage, AnalysisWarningCode, AnalysisErrorCode, AnalysisFailed,
    TimeSpecification, TimeAssignment, GermplasmGrouping, UnitGrouping, RecordGroupDimension,
    RecordGroupMember, AnovaSpec
)
from breedgraph.domain.model.analysis_context import AnalysisContext, AnalysisRecord
from breedgraph.domain.model.time_descriptors import upper
from breedgraph.domain.services.analysis_binning import Binner, parse_datetime
from breedgraph.domain.services.analysis_places import Placer, Place
from breedgraph.domain.services.record_grouping_resolver import RecordGroupDimensionResolver


@dataclass(frozen=True)
class DimensionLevel:
    """
    The level of a dimension assigned to a record.

    key identifies the level within the dimension.
    output is the value of the dimension in AnalysisGroup.
    """
    key: str
    output: Any = None
    # raw attributes used to build exclusion rules for an observation
    start: datetime64 | None = None
    end: datetime64 | None = None
    member: RecordGroupMember | None = None


class DimensionResolver(ABC):
    warning_code: AnalysisWarningCode
    description: str

    def __init__(self, reference: AnalysisTermReference, path: list[str]):
        """
        :param reference: the term reference representing this dimension, its label names the frame column
        :param path: input path of the dimension configuration, for messages
        """
        self.reference = reference
        self.path = path
        self.unassigned: list[int] = []

    @property
    def name(self) -> str:
        return self.reference.label

    def assign(self, record: AnalysisRecord) -> DimensionLevel | None:
        level = self._assign(record)
        if level is None:
            self.unassigned.append(record.record_id)
        return level

    @abstractmethod
    def _assign(self, record: AnalysisRecord) -> DimensionLevel | None:
        ...

    def warnings(self) -> list[AnalysisMessage]:
        if not self.unassigned:
            return []
        return [AnalysisMessage(
            code=self.warning_code,
            message=f"{len(self.unassigned)} records could not be assigned to {self.description} and were excluded",
            path=self.path,
            record_ids=sorted(self.unassigned)
        )]


class UnitResolver(DimensionResolver):
    """The observation unit: the base unit of each record, or its closest selected parent unit."""
    warning_code = AnalysisWarningCode.UNASSIGNED_UNIT
    description = "a unit"

    def __init__(self, grouping: UnitGrouping | None, path: list[str]):
        super().__init__(AnalysisTermReference(type=AnalysisTermType.UNIT), path)
        self.selected = set(grouping.unit_ids) if grouping is not None else None

    def _assign(self, record: AnalysisRecord) -> DimensionLevel | None:
        unit = record.unit
        if unit is None:
            return None
        if self.selected is None or unit.unit_id in self.selected:
            unit_id = unit.unit_id
        else:
            unit_id = next((a for a in unit.ancestor_ids if a in self.selected), None)
            if unit_id is None:
                return None
        return DimensionLevel(key=str(unit_id), output=unit_id)


class TimeResolver(DimensionResolver):
    warning_code = AnalysisWarningCode.UNASSIGNED_TIME
    description = "a time bin"

    def __init__(self, specification: TimeSpecification, path: list[str]):
        super().__init__(AnalysisTermReference(type=AnalysisTermType.TIME), path)
        self.specification = specification
        try:
            self.binner = Binner(specification.binning, parse_datetime)
        except ValueError as e:
            raise AnalysisFailed.single(AnalysisErrorCode.CONFIG_INVALID, str(e), path=path + ['binning', 'boundaries'])

    def record_time(self, record: AnalysisRecord) -> datetime64 | None:
        """
        The time of a record within its period, which runs from the start of the period of its start to the end of the
        period of its end, either standing in for a missing other (see time_descriptors.upper): START is the first
        moment of the period, END its last and MIDPOINT its middle. A record ending 2021-05-03 ends late that day,
        and one dated 2021 has its midpoint in July
        """
        start = record.start if record.start is not None else record.end
        end = record.end if record.end is not None else record.start
        if start is None:
            return None
        # the end of the period is exclusive, so END is the millisecond before it
        start, end = datetime64(start, 'ms'), datetime64(upper(end), 'ms')
        assignment = self.specification.assignment
        if assignment == TimeAssignment.START:
            return start
        if assignment == TimeAssignment.END:
            return end - timedelta64(1, 'ms')
        return start + (end - start) / 2

    def _assign(self, record: AnalysisRecord) -> DimensionLevel | None:
        time = self.record_time(record)
        if time is None:
            return None
        time_bin = self.binner.bin(datetime64(time, 'ms'))
        return DimensionLevel(key=time_bin.label, output=time_bin.label, start=time_bin.lower, end=time_bin.upper)


class GermplasmResolver(DimensionResolver):
    """
    Assigns the germplasm of each base unit to the closest selected germplasm, itself or an ancestor; with none
    selected, to itself.
    """
    warning_code = AnalysisWarningCode.UNASSIGNED_GERMPLASM

    def __init__(self, grouping: GermplasmGrouping, descendants: dict[int, set[int]], path: list[str]):
        super().__init__(AnalysisTermReference(type=AnalysisTermType.GERMPLASM), path)
        self.descendants = {g: descendants.get(g, set()) for g in grouping.germplasm_ids}
        self.description = "a selected germplasm" if self.descendants else "a germplasm"
        self._assigned: dict[int, int | None] = {}

    def _closest(self, germplasm_id: int) -> int | None:
        if not self.descendants:
            return germplasm_id
        candidates = [
            selected for selected, descendants in self.descendants.items()
            if germplasm_id == selected or germplasm_id in descendants
        ]
        if not candidates:
            return None
        # the closest candidate is a descendant of every other candidate
        for candidate in candidates:
            if all(candidate == other or candidate in self.descendants[other] for other in candidates):
                return candidate
        return None  # ambiguous: selected germplasm on separate lineages

    def _assign(self, record: AnalysisRecord) -> DimensionLevel | None:
        if record.unit is None or record.unit.germplasm_id is None:
            return None
        germplasm_id = record.unit.germplasm_id
        if germplasm_id not in self._assigned:
            self._assigned[germplasm_id] = self._closest(germplasm_id)
        selected = self._assigned[germplasm_id]
        if selected is None:
            return None
        return DimensionLevel(key=str(selected), output=selected)


class PositionDimensionResolver(DimensionResolver):
    """
    A level of where the record's unit was, from the place shared by the position dimensions
    (domain.services.analysis_places). Every position dimension is assigned or none is, so the location dimension
    alone reports the records it could not place.
    """
    warning_code = AnalysisWarningCode.UNASSIGNED_POSITION
    description = "a position at a location of the selected types"

    def __init__(self, reference: AnalysisTermReference, placer: Placer, path: list[str], reports: bool = False):
        super().__init__(reference, path)
        self.placer = placer
        self.reports = reports

    def _assign(self, record: AnalysisRecord) -> DimensionLevel | None:
        place = self.placer.place(record)
        return self._level(place) if place is not None else None

    @abstractmethod
    def _level(self, place: Place) -> DimensionLevel:
        ...

    def warnings(self) -> list[AnalysisMessage]:
        return super().warnings() if self.reports else []


class LocationResolver(PositionDimensionResolver):
    def _level(self, place: Place) -> DimensionLevel:
        return DimensionLevel(key=str(place.location_id), output=place.location_id)


class LayoutAxisResolver(PositionDimensionResolver):
    """An axis's values are nested in the layout that has the axis, so row 3 of one field is not row 3 of another"""

    def __init__(self, reference: AnalysisTermReference, index: int, placer: Placer, path: list[str]):
        super().__init__(reference, placer, path)
        self.index = index

    def _level(self, place: Place) -> DimensionLevel:
        axis, layout_id, value = place.axes[self.index]
        return DimensionLevel(
            key=f"{layout_id}|{value}", output={'axis': axis, 'layout_id': layout_id, 'value': value}
        )


class StudyResolver(DimensionResolver):
    warning_code = AnalysisWarningCode.UNASSIGNED_UNIT  # every record belongs to a study
    description = "a study"

    def __init__(self, path: list[str]):
        super().__init__(AnalysisTermReference(type=AnalysisTermType.STUDY), path)

    def _assign(self, record: AnalysisRecord) -> DimensionLevel | None:
        return DimensionLevel(key=str(record.study_id), output=record.study_id)


class RecordGroupResolver(DimensionResolver):
    warning_code = AnalysisWarningCode.UNASSIGNED_RECORD_GROUP

    def __init__(self, dimension: RecordGroupDimension, context: AnalysisContext, path: list[str]):
        super().__init__(dimension.reference, path)
        self.description = f"record group dimension '{dimension.name}'"
        self.resolver = RecordGroupDimensionResolver(
            dimension=dimension,
            studies=context.studies.values(),
            dataset_studies=context.dataset_studies,
            path=path,
            within_unit=set(context.within_unit_groupings),
            within_graph=set(context.within_graph_groupings),
            units=context.units
        )
        if self.resolver.nested_in_unit:
            self._check_replicates(dimension, context, path)

    @staticmethod
    def _check_replicates(dimension: RecordGroupDimension, context: AnalysisContext, path: list[str]):
        """
        A dimension of WITHIN_UNIT groupings keeps each replicate as an observation, for analyses of readings.
        Its levels are only meaningful within a unit, so it can't be a term,
        and in a statistical model the replicates would be counted as independent observations.
        """
        spec = context.request.spec
        spec_path = [context.request.analysis_type.input_field]
        for reference_path, reference in spec.references():
            if reference == dimension.reference:
                raise AnalysisFailed.single(
                    AnalysisErrorCode.CONFIG_INVALID,
                    f"Record group dimension '{dimension.name}' has WITHIN_UNIT groupings, "
                    f"whose codes only distinguish records within a unit, so it can't be used as a term",
                    path=spec_path + reference_path
                )
        if isinstance(spec, AnovaSpec):
            raise AnalysisFailed.single(
                AnalysisErrorCode.CONFIG_INVALID,
                f"Record group dimension '{dimension.name}' has WITHIN_UNIT groupings, which would keep replicates "
                f"as independent observations in the model; remove it and set a replicateAggregation on the terms",
                path=path
            )

    def _assign(self, record: AnalysisRecord) -> DimensionLevel | None:
        root_id = record.unit.root_id if record.unit is not None else None
        assignment = self.resolver.assign(record.dataset_id, record.groups, record.unit_id, root_id)
        if assignment is None:
            return None
        return DimensionLevel(key=assignment.level, output=assignment.to_output(), member=assignment.member)

    def warnings(self) -> list[AnalysisMessage]:
        return super().warnings() + self.resolver.warnings()


def build_dimension_resolvers(context: AnalysisContext) -> list[DimensionResolver]:
    """Resolvers for the dimensions of observation identity, in a stable order with the unit first."""
    spec = context.request.spec
    grouping = spec.grouping
    path = [context.request.analysis_type.input_field, 'grouping']
    resolvers: list[DimensionResolver] = [UnitResolver(grouping.unit, path + ['unit'])]
    if grouping.time is not None:
        resolvers.append(TimeResolver(grouping.time, path + ['time']))
    if grouping.germplasm is not None:
        resolvers.append(GermplasmResolver(grouping.germplasm, context.germplasm_descendants, path + ['germplasm']))
    if grouping.position is not None:
        resolvers += position_resolvers(context, path + ['position'])
    for i, dimension in enumerate(grouping.record_groups):
        resolvers.append(RecordGroupResolver(dimension, context, path + ['recordGroups', str(i)]))
    if any(t.reference.type == AnalysisTermType.STUDY for t in spec.terms):
        resolvers.append(StudyResolver([context.request.analysis_type.input_field, 'terms']))
    return resolvers


def position_resolvers(context: AnalysisContext, path: list[str]) -> list[PositionDimensionResolver]:
    """The location dimension, then one for each axis, sharing their placements"""
    grouping = context.request.spec.grouping.position
    placer = Placer(grouping, context)
    location, *axes = grouping.references
    return [LocationResolver(location, placer, path, reports=True)] + [
        LayoutAxisResolver(reference, i, placer, path) for i, reference in enumerate(axes)
    ]


def context_levels(resolvers: list[DimensionResolver], record: AnalysisRecord) -> dict[str, DimensionLevel | None] | None:
    """
    The levels of a factor record describing the observations of variable records, by dimension name.
    None for a dimension it applies across: time when it has none, record groups it has no code for,
    and germplasm and position, which come from the observed unit. The unit level is its own unit or the selected
    parent unit it rolls up to, or None when it is above the selected units (it may still apply to their descendants).
    Returns None, and reports the record as unassigned to a unit, if it has no unit.
    """
    unit_resolver = resolvers[0]
    if record.unit is None:
        unit_resolver.assign(record)
        return None
    levels = {}
    for resolver in resolvers:
        if isinstance(resolver, (GermplasmResolver, PositionDimensionResolver)):
            levels[resolver.name] = None
        else:
            # unlike assign, a level the record has none of is not reported: the record applies across it
            levels[resolver.name] = resolver._assign(record)
    return levels
