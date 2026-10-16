from breedgraph.domain.model.time_descriptors import local_datetime64
from pydantic import BaseModel, Field

from breedgraph.domain.model.contributions import Contribution, ContributionInput
from breedgraph.domain.model.datasets import DatasetInput, DataRecordInput, RecordGroup, DataRecordUpdate


class RecordImport(BaseModel):
    unit_id: int
    start: str | None = None
    end: str | None = None
    value: str | int | None = None
    groups: list[RecordGroup] | None = None
    reference_ids: list[int] | None = None

class RecordUpdateImport(BaseModel):
    id: int
    start: str | None
    end: str | None
    value: str | int | None
    groups: list[RecordGroup] | None = None
    reference_ids: list[int] | None = None

class DatasetImportBase(BaseModel):
    study_id: int | None = None
    concept_id: int | None = None
    records: list[RecordImport|RecordUpdateImport] = Field(default_factory=list)
    contributions: list[ContributionInput] | None = None
    reference_ids: list[int] | None = None

    def contributions_to_input(self) -> list[Contribution] | None:
        if self.contributions is None:
            return None
        return [contribution.to_contribution() for contribution in self.contributions]

    def records_to_input(self) -> list[DataRecordInput]:
        return [
            DataRecordInput(
                unit=r.unit_id if hasattr(r, 'unit_id') else None,
                start=local_datetime64(r.start) if r.start else None,
                end=local_datetime64(r.end) if r.end else None,
                value=r.value,
                groups=r.groups,
                references=r.reference_ids
            )
            for r in self.records
        ]

    def records_to_update(self) -> list[DataRecordUpdate]:
        update_records = []
        for r in self.records:
            if not isinstance(r, RecordUpdateImport):
                raise ValueError("Records must be of type RecordUpdateImport for updates")

            update_records.append(
                DataRecordUpdate(
                    id=r.id,
                    unit=r.unit_id if hasattr(r, 'unit_id') else None,
                    start=local_datetime64(r.start) if r.start else None,
                    end=local_datetime64(r.end) if r.end else None,
                    value=r.value if r.value is not None else None,
                    groups=r.groups if r.groups is not None else None,
                    references=r.reference_ids if r.reference_ids is not None else None
                )
            )

        return update_records

class DatasetImport(DatasetImportBase):
    study_id: int
    concept_id: int
    records: list[RecordImport] = Field(default_factory=list)

    def to_input_for_create(self) -> DatasetInput:
        return DatasetInput(
            study_id=self.study_id,
            concept_id=self.concept_id,
            contributions=self.contributions_to_input() or [],
            reference_ids=self.reference_ids,
            records=[
                DataRecordInput(
                    unit = r.unit_id,
                    start = local_datetime64(r.start) if r.start else None,
                    end = local_datetime64(r.end) if r.end else None,
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
