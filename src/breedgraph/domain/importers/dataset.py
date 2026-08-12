from pydantic import BaseModel, Field

from breedgraph.domain.model.datasets import DatasetInput

class RecordImport(BaseModel):
    unit_id: int
    start: str | None = None
    end: str | None = None
    value: str | int | None = None
    reference_ids: list[int] = Field(default_factory=list)

class RecordUpdateImport(BaseModel):
    id: int
    start: str | None = None
    end: str | None = None
    value: str | int | None = None
    reference_ids: list[int] = Field(default_factory=list)

class DatasetImportBase(BaseModel):
    study_id: int | None = None
    concept_id: int | None = None
    records: list[RecordImport|RecordUpdateImport] = Field(default_factory=list)
    contributor_ids: list[int] | None = None
    reference_ids: list[int] | None = None

    def dump_records(self) -> list[dict[str, str | int | None | list]]:
        return [
            r.model_dump() for r in self.records
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
        )

class DatasetUpdateImport(DatasetImportBase):
    dataset_id: int
    records: list[RecordUpdateImport] = Field(default_factory=list)
