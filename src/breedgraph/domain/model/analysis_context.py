"""
Data loaded to prepare an analysis, as readable by the requesting user.
"""
from dataclasses import dataclass, field
from functools import cached_property
from typing import Iterator

from numpy import datetime64

from breedgraph.domain.model.analysis import AnalysisRequest, AnalysisTermType
from breedgraph.domain.model.unit_graphs import Position
from breedgraph.domain.model.datasets import DatasetStored, RecordGroup
from breedgraph.domain.model.ontology import ScaleType, RecordGroupExtent
from breedgraph.domain.model.programs import StudyStored, RecordGroupingStored


@dataclass
class UnitContext:
    unit_id: int
    subject_id: int | None = None  # None if the unit is hidden from the user
    # its own germplasm, or the one the nearest units above it with germplasm agree on (domain.services.lineages)
    germplasm_id: int | None = None
    positions: list[Position] = field(default_factory=list)
    ancestor_ids: list[int] = field(default_factory=list)  # closest first
    parent_ids: list[int] = field(default_factory=list)  # the nearest units above it that the user can read
    root_id: int | None = None  # root of its graph, even if hidden from the user, for WITHIN_GRAPH codes
    readable: bool = True  # False for a placeholder of a hidden unit with records
    # the nearest units above it that the user can read or that are hidden with positions, which stop a placement
    # (docs/read-access.md, rule 3); only loaded for position grouping
    place_parent_ids: list[int] = field(default_factory=list)

@dataclass
class LocationContext:
    """A location in the location tree as the user sees it, hidden locations skipped (docs/read-access.md, rule 3)"""
    location_id: int
    type_id: int | None = None
    parent_id: int | None = None
    readable: bool = True  # False for the placeholder of a hidden root

@dataclass
class LayoutContext:
    """A layout in its layout tree as the user sees it, hidden layouts skipped (docs/read-access.md, rule 3)"""
    layout_id: int
    axes: list[str] = field(default_factory=list)
    parent_id: int | None = None
    # its position in the parent layout's axes; None for a root, or where a hidden layout was skipped
    position: list | None = None
    readable: bool = True  # False for the placeholder of a hidden root

@dataclass
class ConceptContext:
    concept_id: int
    scale_type: ScaleType
    categories: list[str] | None = None  # category names, ordered by rank for ordinal scales
    factor: bool = False  # a factor describes the conditions of units, a variable is observed on them

@dataclass
class AnalysisRecord:
    """A record of a selected dataset with the attributes used to prepare an analysis."""
    record_id: int
    dataset_id: int
    study_id: int
    concept_id: int
    unit_id: int | None
    value: str | None
    start: datetime64 | None
    end: datetime64 | None
    groups: list[RecordGroup]
    unit: UnitContext | None  # None if the unit was not found


@dataclass
class AnalysisContext:
    request: AnalysisRequest
    datasets: dict[int, DatasetStored]
    concepts: dict[int, ConceptContext]
    units: dict[int, UnitContext]
    studies: dict[int, StudyStored]
    # selected germplasm ID -> IDs of its descendants, for germplasm grouping
    germplasm_descendants: dict[int, set[int]] = field(default_factory=dict)
    # for position grouping: the locations and layouts of the units' positions with those above them, and the hidden
    # units with positions, which stop a placement
    locations: dict[int, LocationContext] = field(default_factory=dict)
    layouts: dict[int, LayoutContext] = field(default_factory=dict)
    hidden_positioned: set[int] = field(default_factory=set)

    @property
    def dataset_studies(self) -> dict[int, int]:
        return {dataset_id: dataset.study for dataset_id, dataset in self.datasets.items()}

    @property
    def factors_describe_observations(self) -> bool:
        """
        Whether factor records describe the observations of variable records, rather than being observations:
        when any concept term is a variable.
        """
        return any(not concept.factor for concept in self.concepts.values())

    def is_context(self, record: AnalysisRecord) -> bool:
        """Whether the record is a factor record describing the observations of variable records"""
        return self.concepts[record.concept_id].factor and self.factors_describe_observations

    @property
    def concept_ids(self) -> set[int]:
        """Concepts of the CONCEPT terms of the analysis"""
        return {
            term.reference.concept_id for term in self.request.spec.terms
            if term.reference.type == AnalysisTermType.CONCEPT
        }

    @property
    def groupings(self) -> dict[int, RecordGroupingStored]:
        return {
            grouping.id: grouping
            for study in self.studies.values()
            for grouping in study.groupings
            if isinstance(grouping, RecordGroupingStored)
        }

    @cached_property
    def within_unit_groupings(self) -> dict[int, RecordGroupingStored]:
        """Groupings with the WITHIN_UNIT extent: their codes distinguish replicates of a unit."""
        return {
            grouping_id: grouping for grouping_id, grouping in self.groupings.items()
            if grouping.extent == RecordGroupExtent.WITHIN_UNIT
        }

    @cached_property
    def within_graph_groupings(self) -> dict[int, RecordGroupingStored]:
        """Groupings with the WITHIN_GRAPH extent: their codes are nested in the root of the unit's graph."""
        return {
            grouping_id: grouping for grouping_id, grouping in self.groupings.items()
            if grouping.extent == RecordGroupExtent.WITHIN_GRAPH
        }

    def replicate_key(self, record: AnalysisRecord) -> tuple | None:
        """
        Records with the same key can be replicates of one reading, depending on their times:
        the same base unit, with codes of the same WITHIN_UNIT groupings and scopes.
        None if the record has no such codes.
        """
        scopes = tuple(sorted(
            (group.id, self.within_unit_groupings[group.id].scope_key(record.dataset_id) or frozenset())
            for group in record.groups if group.id in self.within_unit_groupings
        ))
        if not scopes:
            return None
        return record.unit_id, scopes

    def records(self) -> Iterator[AnalysisRecord]:
        """
        Records of the selected datasets whose concepts are used by the analysis,
        in dataset order then by ID, so observations are in a reproducible order.
        """
        concept_ids = self.concept_ids
        for dataset_id in self.request.dataset_ids:
            dataset = self.datasets.get(dataset_id)
            if dataset is None or dataset.concept not in concept_ids:
                continue
            for record in sorted(dataset.records, key=lambda r: r.id):
                yield AnalysisRecord(
                    record_id=record.id,
                    dataset_id=dataset.id,
                    study_id=dataset.study,
                    concept_id=dataset.concept,
                    unit_id=record.unit,
                    value=record.value,
                    start=record.start,
                    end=record.end,
                    groups=list(record.groups or []),
                    unit=self.units.get(record.unit) if record.unit is not None else None
                )
