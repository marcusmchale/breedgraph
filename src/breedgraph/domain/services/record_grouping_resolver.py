from dataclasses import dataclass, replace
from typing import Iterable

from breedgraph.domain.model.analysis import (
    RecordGroupDimension, RecordGroupLevelKey, RecordGroupMember,
    AnalysisFailed, AnalysisErrorCode, AnalysisMessage, AnalysisWarningCode
)
from breedgraph.domain.model.analysis_context import UnitContext
from breedgraph.domain.model.datasets import RecordGroup
from breedgraph.domain.model.programs import StudyStored, GroupingScope, RecordGroupingStored


@dataclass(frozen=True)
class RecordGroupAssignment:
    """The level of a record group dimension assigned to a record."""
    dimension: str
    level: str  # unique within the dimension: shared label, nested level key or unit level key
    nested: RecordGroupLevelKey | None = None  # None for shared levels and unit levels
    member: RecordGroupMember | None = None  # the code of the record, for exclusion rules
    unit_id: int | None = None  # the unit of a unit level

    @classmethod
    def of_unit(cls, dimension: str, unit_id: int) -> 'RecordGroupAssignment':
        # nested keys have three or four parts and shared labels can't contain "|", so this key is unique
        return cls(dimension=dimension, level=f"unit|{unit_id}", unit_id=unit_id)

    def to_output(self) -> dict:
        nested = self.nested
        return {
            'dimension': self.dimension,
            'level': self.level,
            'shared': nested is None and self.unit_id is None,
            'grouping_id': nested.grouping_id if nested else None,
            'scope_dataset_ids': sorted(nested.scope) if nested and nested.scope is not None else None,
            'code': nested.code if nested else None,
            'unit_id': nested.unit if nested else self.unit_id,
        }


class RecordGroupDimensionResolver:
    """
    Assigns records to the levels of a record group dimension.

    Each (grouping, scope, code) is a distinct level unless combined
    into a shared level by the dimension's level definitions.
    Codes of WITHIN_UNIT groupings are also nested in the base unit, and can't be shared.
    Codes of WITHIN_GRAPH groupings are nested in the root of the base unit's graph;
    a shared level definition combines a code across graphs.
    Groupings are resolved live, as readable by the requesting user.

    Records of studies without one of the groupings take a unit level instead: the nearest unit of one of the
    dimension's subjects, the base unit or an ancestor, so each study has one source of levels.
    Only the units the user can read have a subject.
    """

    def __init__(
            self,
            dimension: RecordGroupDimension,
            studies: Iterable[StudyStored],
            dataset_studies: dict[int, int],
            path: list[str] | None = None,
            within_unit: set[int] | None = None,
            within_graph: set[int] | None = None,
            units: dict[int, UnitContext] | None = None
    ):
        """
        :param dimension: the dimension to resolve
        :param studies: studies of the selected datasets, as readable by the requesting user
        :param dataset_studies: selected dataset ID -> study ID
        :param path: input path of the dimension, for messages
        :param within_unit: IDs of the groupings with the WITHIN_UNIT extent
        :param within_graph: IDs of the groupings with the WITHIN_GRAPH extent
        :param units: units of the records and their ancestors, for unit levels
        """
        self.dimension = dimension
        self.dataset_studies = dataset_studies
        self.within_unit = within_unit or set()
        self.within_graph = within_graph or set()
        self.units = units or {}
        self.subject_ids = set(dimension.subject_ids)
        self._unit_levels: dict[int, int | None] = {}  # base unit -> unit level
        self.path = path or []
        self.groupings: dict[int, RecordGroupingStored] = {}
        self.grouping_study: dict[int, int] = {}
        self.observed: set[RecordGroupLevelKey] = set()

        selected_studies = set(dataset_studies.values())
        for study in studies:
            if study.id not in selected_studies:
                continue
            # Redacted studies have no groupings, so unreadable groupings are reported as missing
            for grouping in study.groupings:
                if isinstance(grouping, RecordGroupingStored) and grouping.id in dimension.grouping_ids:
                    self.groupings[grouping.id] = grouping
                    self.grouping_study[grouping.id] = study.id

        missing = [gid for gid in dimension.grouping_ids if gid not in self.groupings]
        if missing:
            raise AnalysisFailed([
                AnalysisMessage(
                    code=AnalysisErrorCode.GROUPING_NOT_FOUND,
                    message=(
                        f"Record grouping {gid} in dimension '{dimension.name}' was not found "
                        f"in the studies of the selected datasets, or is not readable"
                    ),
                    path=self.path + ['groupingIds', str(dimension.grouping_ids.index(gid))]
                ) for gid in missing
            ])

        grouping_by_study: dict[int, int] = {}
        for grouping_id, study_id in self.grouping_study.items():
            if study_id in grouping_by_study:
                raise AnalysisFailed.single(
                    AnalysisErrorCode.CONFIG_INVALID,
                    f"Groupings {grouping_by_study[study_id]} and {grouping_id} in dimension "
                    f"'{dimension.name}' belong to the same study",
                    path=self.path + ['groupingIds']
                )
            grouping_by_study[study_id] = grouping_id
        self.coded_studies = set(grouping_by_study)  # studies whose records take their levels from codes

        self.shared: dict[RecordGroupLevelKey, str] = {}
        for i, level in enumerate(dimension.levels):
            for j, member in enumerate(level.members):
                member_path = self.path + ['levels', str(i), 'members', str(j)]
                nested = self._member_level(member, member_path)
                if nested in self.shared:
                    raise AnalysisFailed.single(
                        AnalysisErrorCode.CONFIG_INVALID,
                        f"Code '{member.code}' of grouping {member.grouping_id} is assigned to levels "
                        f"'{self.shared[nested]}' and '{level.label}' in dimension '{dimension.name}'",
                        path=member_path
                    )
                self.shared[nested] = level.label

    @property
    def nested_in_unit(self) -> bool:
        """Whether any grouping of the dimension has the WITHIN_UNIT extent."""
        return any(grouping_id in self.within_unit for grouping_id in self.groupings)

    def _level(
            self,
            grouping: RecordGroupingStored,
            dataset_id: int | None,
            code: str,
            unit_id: int | None = None,
            root_id: int | None = None
    ) -> RecordGroupLevelKey:
        if grouping.id in self.within_unit:
            unit = unit_id
        elif grouping.id in self.within_graph:
            unit = root_id
        else:
            unit = None
        return RecordGroupLevelKey(grouping_id=grouping.id, scope=grouping.scope_key(dataset_id), code=code.strip(), unit=unit)

    def _member_level(self, member: RecordGroupMember, path: list[str]) -> RecordGroupLevelKey:
        grouping = self.groupings[member.grouping_id]
        if grouping.id in self.within_unit:
            raise AnalysisFailed.single(
                AnalysisErrorCode.CONFIG_INVALID,
                f"Code '{member.code}' of grouping {grouping.id} can't be in a shared level: "
                f"its codes only distinguish records within a unit (WITHIN_UNIT)",
                path=path
            )
        if grouping.scope == GroupingScope.DATASET_SCOPED:
            if member.dataset_id is None:
                raise AnalysisFailed.single(
                    AnalysisErrorCode.CONFIG_INVALID,
                    f"A dataset is required to identify the scope of code '{member.code}' "
                    f"in dataset-scoped grouping {grouping.id}",
                    path=path + ['datasetId']
                )
            if self.dataset_studies.get(member.dataset_id) != self.grouping_study[grouping.id]:
                raise AnalysisFailed.single(
                    AnalysisErrorCode.CONFIG_INVALID,
                    f"Dataset {member.dataset_id} is not a selected dataset "
                    f"of the study of grouping {grouping.id}",
                    path=path + ['datasetId']
                )
        elif member.dataset_id is not None:
            raise AnalysisFailed.single(
                AnalysisErrorCode.CONFIG_INVALID,
                f"A dataset must not be provided for code '{member.code}' "
                f"of study-wide grouping {grouping.id}",
                path=path + ['datasetId']
            )
        return self._level(grouping, member.dataset_id, member.code)

    def assign(
            self,
            dataset_id: int,
            groups: list[RecordGroup] | None,
            unit_id: int | None = None,
            root_id: int | None = None
    ) -> RecordGroupAssignment | None:
        """
        Level of a record in this dimension, or None if the record has no code for any grouping of the dimension,
        or in a study without one, no unit of the dimension's subjects, and should be excluded.
        unit_id is the record's base unit, which nests the codes of WITHIN_UNIT groupings and finds unit levels,
        and root_id the root of its graph, which nests the codes of WITHIN_GRAPH groupings.
        """
        if self.dataset_studies.get(dataset_id) not in self.coded_studies:
            level = self._unit_level(unit_id)
            return RecordGroupAssignment.of_unit(self.dimension.name, level) if level is not None else None

        matches = [group for group in groups or [] if group.id in self.groupings]
        if not matches:
            return None
        if len(matches) > 1:
            # Unreachable while one grouping per study and one code per grouping are enforced
            raise ValueError(f"Record has more than one code for dimension '{self.dimension.name}'")

        group = matches[0]
        grouping = self.groupings[group.id]
        if self.dataset_studies.get(dataset_id) != self.grouping_study[grouping.id]:
            # Record codes are validated against study groupings on submission
            raise ValueError(
                f"Dataset {dataset_id} has codes for grouping {grouping.id} of another study"
            )

        level = self._level(grouping, dataset_id, group.code, unit_id, root_id)
        # Shared level definitions name a code of a WITHIN_GRAPH grouping in every graph
        defined = replace(level, unit=None) if grouping.id in self.within_graph else level
        self.observed.add(defined)
        member = RecordGroupMember(
            grouping_id=grouping.id,
            code=level.code,
            dataset_id=dataset_id if grouping.scope == GroupingScope.DATASET_SCOPED else None
        )
        label = self.shared.get(defined)
        if label is not None:
            return RecordGroupAssignment(dimension=self.dimension.name, level=label, member=member)
        return RecordGroupAssignment(dimension=self.dimension.name, level=level.key, nested=level, member=member)

    def _unit_level(self, unit_id: int | None) -> int | None:
        if not self.subject_ids or unit_id is None:
            return None
        if unit_id not in self._unit_levels:
            self._unit_levels[unit_id] = self._nearest_unit(unit_id)
        return self._unit_levels[unit_id]

    def _nearest_unit(self, unit_id: int) -> int | None:
        """
        The nearest unit of one of the subjects, the unit itself or an ancestor, if it is below every other one;
        None if there is none, or they lie on separate lineages (e.g. a sample taken from trees of two plots).
        """
        unit = self.units.get(unit_id)
        if unit is None:
            return None
        candidates = [
            candidate for candidate in [unit_id, *unit.ancestor_ids]
            if candidate in self.units and self.units[candidate].subject_id in self.subject_ids
        ]
        if not candidates:
            return None
        # ancestors are sorted closest first, so the first candidate is the nearest, or one of the nearest
        nearest, *others = candidates
        above = set(self.units[nearest].ancestor_ids)
        return nearest if all(other in above for other in others) else None

    def unmatched_members(self) -> list[tuple[str, RecordGroupLevelKey]]:
        """(level label, member) for shared level members that matched no records, for warnings."""
        return [(label, level) for level, label in self.shared.items() if level not in self.observed]

    def warnings(self) -> list[AnalysisMessage]:
        return [
            AnalysisMessage(
                code=AnalysisWarningCode.RECORD_GROUP_LEVEL_UNMATCHED,
                message=(
                    f"Code '{level.code}' of grouping {level.grouping_id} in level '{label}' "
                    f"of dimension '{self.dimension.name}' matched no records"
                ),
                path=self.path + ['levels']
            )
            for label, level in self.unmatched_members()
        ]

    def member_matches(self, member: RecordGroupMember, dataset_id: int, groups: list[RecordGroup] | None) -> bool:
        """Whether a record has the given code, within the member's scope."""
        return record_has_member(self.groupings.get(member.grouping_id), member, dataset_id, groups)


def record_has_member(
        grouping: RecordGroupingStored | None,
        member: RecordGroupMember,
        dataset_id: int,
        groups: list[RecordGroup] | None
) -> bool:
    """
    Whether a record of a dataset has the code of a record group member.
    For dataset-scoped groupings the record dataset must share the member's scope.
    """
    if grouping is None:
        return False
    if not any(g.id == member.grouping_id and g.code.strip() == member.code for g in groups or []):
        return False
    if grouping.scope == GroupingScope.DATASET_SCOPED:
        if member.dataset_id is None:
            return False
        return grouping.scope_key(dataset_id) == grouping.scope_key(member.dataset_id)
    return True
