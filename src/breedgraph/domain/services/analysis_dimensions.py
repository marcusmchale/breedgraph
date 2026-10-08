"""
Resolvers assigning records to the levels of the dimensions of analytical observation identity.

A record that cannot be assigned to a configured dimension is excluded from the analysis,
and reported in one warning per dimension.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from numpy import datetime64

from breedgraph.domain.model.analysis import (
    AnalysisTermType, AnalysisTermReference, AnalysisMessage, AnalysisWarningCode, AnalysisErrorCode, AnalysisFailed,
    TimeSpecification, TimeAssignment, GermplasmGrouping, UnitGrouping, PositionGrouping, RecordGroupDimension,
    RecordGroupMember, intervals_overlap
)
from breedgraph.domain.model.analysis_context import AnalysisContext, AnalysisRecord
from breedgraph.domain.model.blocks import Position
from breedgraph.domain.services.analysis_binning import Binner, parse_datetime
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
        start, end = record.start, record.end
        if start is None or end is None:
            return start if start is not None else end
        assignment = self.specification.assignment
        if assignment == TimeAssignment.START:
            return start
        if assignment == TimeAssignment.END:
            return end
        start, end = datetime64(start, 'ms'), datetime64(end, 'ms')
        return start + (end - start) / 2

    def _assign(self, record: AnalysisRecord) -> DimensionLevel | None:
        time = self.record_time(record)
        if time is None:
            return None
        time_bin = self.binner.bin(datetime64(time, 'ms'))
        return DimensionLevel(key=time_bin.label, output=time_bin.label, start=time_bin.lower, end=time_bin.upper)


class GermplasmResolver(DimensionResolver):
    """Assigns the germplasm of each base unit to the closest selected germplasm, itself or an ancestor."""
    warning_code = AnalysisWarningCode.UNASSIGNED_GERMPLASM
    description = "a selected germplasm"

    def __init__(self, grouping: GermplasmGrouping, descendants: dict[int, set[int]], path: list[str]):
        super().__init__(AnalysisTermReference(type=AnalysisTermType.GERMPLASM), path)
        self.descendants = {g: descendants.get(g, set()) for g in grouping.germplasm_ids}
        self._assigned: dict[int, int | None] = {}

    def _closest(self, germplasm_id: int) -> int | None:
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


class PositionResolver(DimensionResolver):
    """
    Assigns the base unit of each record to a position group.

    Units are matched by location (and layout), at the specified time or at any time.
    Groups are defined by an explicit matching position, otherwise by the values of the
    selected layout axes, otherwise by the location (and layout).
    A unit matching more than one group is not assigned.
    """
    warning_code = AnalysisWarningCode.UNASSIGNED_POSITION
    description = "a position"

    def __init__(self, grouping: PositionGrouping, path: list[str]):
        super().__init__(AnalysisTermReference(type=AnalysisTermType.POSITION), path)
        self.grouping = grouping
        self._assigned: dict[int, DimensionLevel | None] = {}

    def _matches(self, position: Position) -> bool:
        grouping = self.grouping
        if position.location_id != grouping.location_id:
            return False
        if grouping.layout_id is not None and position.layout_id != grouping.layout_id:
            return False
        if grouping.time is not None:
            # the position is occupied at the time: start <= time < end
            return intervals_overlap(position.start, position.end, grouping.time, grouping.time + 1)
        return True

    @staticmethod
    def _coordinates(position: Position) -> list[str | None]:
        return [str(c) if c is not None else None for c in position.coordinates or []]

    def _group(self, position: Position) -> tuple[str, dict]:
        grouping = self.grouping
        coordinates = self._coordinates(position)
        for explicit in grouping.positions or []:
            explicit_coordinates = self._coordinates(explicit)
            if (
                    explicit.location_id == position.location_id
                    and (explicit.layout_id is None or explicit.layout_id == position.layout_id)
                    and explicit_coordinates == coordinates[:len(explicit_coordinates)]
            ):
                return self._level(explicit.location_id, explicit.layout_id, explicit_coordinates)
        if grouping.axis_indexes:
            # values of unselected axes are not part of the group
            selected = [c if i in grouping.axis_indexes else None for i, c in enumerate(coordinates)]
            return self._level(position.location_id, position.layout_id, selected)
        return self._level(position.location_id, grouping.layout_id, None)

    @staticmethod
    def _level(location_id: int, layout_id: int | None, coordinates: list[str | None] | None) -> tuple[str, dict]:
        key = f"{location_id}|{layout_id if layout_id is not None else '*'}|{','.join(c or '' for c in coordinates or [])}"
        return key, {'location_id': location_id, 'layout_id': layout_id, 'coordinates': coordinates}

    def _assign(self, record: AnalysisRecord) -> DimensionLevel | None:
        unit = record.unit
        if unit is None:
            return None
        if unit.unit_id not in self._assigned:
            groups = dict(self._group(p) for p in unit.positions if self._matches(p))
            if len(groups) == 1:
                key, output = next(iter(groups.items()))
                self._assigned[unit.unit_id] = DimensionLevel(key=key, output=output)
            else:
                self._assigned[unit.unit_id] = None
        return self._assigned[unit.unit_id]


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
            path=path
        )

    def _assign(self, record: AnalysisRecord) -> DimensionLevel | None:
        assignment = self.resolver.assign(record.dataset_id, record.groups)
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
        resolvers.append(PositionResolver(grouping.position, path + ['position']))
    for i, dimension in enumerate(grouping.record_groups):
        resolvers.append(RecordGroupResolver(dimension, context, path + ['recordGroups', str(i)]))
    if any(t.reference.type == AnalysisTermType.STUDY for t in spec.terms):
        resolvers.append(StudyResolver([context.request.analysis_type.input_field, 'terms']))
    return resolvers
