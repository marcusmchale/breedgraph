"""
Data loaded to prepare an analysis, as readable by the requesting user.
"""
from dataclasses import dataclass, field
from typing import Iterator

from numpy import datetime64

from breedgraph.domain.model.analysis import AnalysisRequest, AnalysisTermType
from breedgraph.domain.model.blocks import Position
from breedgraph.domain.model.datasets import DatasetStored, RecordGroup
from breedgraph.domain.model.ontology import ScaleType
from breedgraph.domain.model.programs import StudyStored, RecordGroupingStored


@dataclass
class UnitContext:
    unit_id: int
    germplasm_id: int | None = None
    positions: list[Position] = field(default_factory=list)
    ancestor_ids: list[int] = field(default_factory=list)  # closest first

@dataclass
class ConceptContext:
    concept_id: int
    scale_type: ScaleType
    categories: list[str] | None = None  # category names, ordered by rank for ordinal scales

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

    @property
    def dataset_studies(self) -> dict[int, int]:
        return {dataset_id: dataset.study for dataset_id, dataset in self.datasets.items()}

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
