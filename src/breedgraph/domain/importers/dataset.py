from numpy import datetime64
from pydantic import BaseModel, Field

from breedgraph.domain.model.datasets import DatasetInput, RecordGroup, DataRecordInput, RecordGroup


class RecordImport(BaseModel):
    unit_id: int
    start: str | None = None
    end: str | None = None
    value: str | int | None = None
    groups: list[RecordGroup] = Field(default_factory=list)
    reference_ids: list[int] = Field(default_factory=list)

class RecordUpdateImport(BaseModel):
    id: int
    start: str | None
    end: str | None
    value: str | int | None
    groups: list[RecordGroup]
    reference_ids: list[int]

class DatasetImportBase(BaseModel):
    study_id: int | None = None
    concept_id: int | None = None
    records: list[RecordImport|RecordUpdateImport] = Field(default_factory=list)
    contributor_ids: list[int] | None = None
    reference_ids: list[int] | None = None

    def records_to_input(self) -> list[DataRecordInput]:
        return [
            DataRecordInput(
                unit=r.unit_id if hasattr(r, 'unit_id') else None,
                start=datetime64(r.start) if r.start else None,
                end=datetime64(r.end) if r.end else None,
                value=r.value,
                groups=r.groups,
                references=r.reference_ids
            )
            for r in self.records
        ]

class DatasetImport(DatasetImportBase):
    study_id: int
    concept_id: int
    records: list[RecordImport] = Field(default_factory=list)

    def to_input_for_create(self) -> DatasetInput:
        return DatasetInput(
            study_id=self.study_id,
            concept_id=self.concept_id,
            contributor_ids=self.contributor_ids,
            reference_ids=self.reference_ids,
            records=[
                DataRecordInput(
                    unit = r.unit_id,
                    start = datetime64(r.start) if r.start else None,
                    end = datetime64(r.end) if r.end else None,
                    value = r.value,
                    groups = r.groups,
                    references  = r.reference_ids
                )
                for r in self.records
            ]
        )

class DatasetUpdateImport(DatasetImportBase):
    dataset_id: int
    # todo: support changing the concept for a dataset as when the otology evolves it may be desirable.
    records: list[RecordUpdateImport] = Field(default_factory=list)
