from dataclasses import dataclass, field, replace, InitVar
from abc import ABC
from typing import List, ClassVar, Set, Dict, Self, Generator
from numpy import datetime64

from src.breedgraph.service_layer.tracking.wrappers import asdict
from src.breedgraph.domain.model.base import LabeledModel, EnumLabeledModel, StoredModel
from src.breedgraph.domain.model.controls import ControlledModel, ControlledAggregate, Access, Controller, ControlledModelLabel

from src.breedgraph.domain.services.value_parsers import ValueParser
from src.breedgraph.domain.model.ontology import ScaleStored, ScaleCategoryStored, ScaleType



@dataclass
class DataRecordBase(ABC):
    label: ClassVar[str] = "Record"
    plural: ClassVar[str] = "Records"

    unit: int|None = None
    value: str|None = None

    start: datetime64|None = None
    end: datetime64|None = None

    references: List[int]|None = field(default_factory=list)
    # to link supporting data in references repository
    # e.g. raw data or another repository with supporting data


@dataclass
class DataRecordInput(DataRecordBase, LabeledModel):
    unit_id: InitVar[int|None] = None
    reference_ids: InitVar[List[int] | None] = None

    def __post_init__(self, unit_id, reference_ids):
        if unit_id is not None:
            self.unit = unit_id
        if reference_ids is not None:
            self.references = reference_ids
        if self.start:
            self.start = datetime64(self.start)
        if self.end:
            self.end = datetime64(self.end)
        if self.start and self.end:
            if self.start > self.end:
                raise ValueError("Start date cannot be after end date")

@dataclass
class DataRecordStored(DataRecordBase, StoredModel):
    submitted: datetime64|None = None

@dataclass
class DataRecordOutput(DataRecordBase, StoredModel):
    submitted: datetime64|None = None

@dataclass(eq=False)
class DatasetBase(ABC):
    """
        DataRecords are aggregated by ontology_id AND study into a Dataset.
        "concept" should reference to Variable or Factor in the ontology.
        "study" should reference to Study in the study repository
        "Records" is a list of DataRecord
        """
    label: ClassVar[str] = ControlledModelLabel.DATASET

    study: int = None
    concept: int = None
    records: List[DataRecordStored|DataRecordInput] = field(default_factory=list)

    contributors: List[int] = field(default_factory=list) # PersonStored that contributed to this dataset by ID
    references: List[int] = field(default_factory=list) # to link supporting data in references repository
    # e.g. raw data or another repository with supporting data

    def add_records(
            self,
            records: List[DataRecordInput|dict],
            scale: ScaleStored,
            categories: List[ScaleCategoryStored]|None
    ) -> Generator[None|str, None, None]:
        for record in records:
            try:
                if isinstance(record, dict):
                    record = DataRecordInput(**record)
                parsed_record = self.parse_record(record, scale, categories)
                self.records.append(parsed_record)
                yield None
            except Exception as e:
                yield str(e)

    def update_records(
            self,
            records: List[DataRecordStored|dict],
            scale: ScaleStored,
            categories: List[ScaleCategoryStored]|None
    ) -> Generator[None|str, None, None]:
        record_index_map = { record.id: record_index for record_index, record in enumerate(self.records) }
        for record in records:
            if isinstance(record, dict):
                record = DataRecordInput(**record)
            try:
                record.value = self.parse_value(record.value, scale, categories)
                record_index = record_index_map[record.id]
                self.records[record_index] = record
                yield None
            except Exception as e:
                yield str(e)

    def remove_records(self, record_ids: List[int]) -> Generator[None|str, None, None]:
        record_index_map = {record.id: record_index for record_index, record in enumerate(self.records)}
        indices_to_remove = set()
        for record_id in record_ids:
            if record_id in record_index_map:
                indices_to_remove.add(record_index_map[record_id])
                yield None
            else:
                yield f"Record with id {record_id} not found in dataset"
        indices_to_remove = list(indices_to_remove)
        indices_to_remove.sort(reverse=True)
        for i in indices_to_remove:
            del self.records[i]

    def model_dump(self):
        dump = asdict(self)
        dump['records'] = [record.model_dump() for record in self.records]
        return dump

    @staticmethod
    def parse_value(value: str|int, scale: ScaleStored, categories: List[ScaleCategoryStored]):
        return ValueParser().parse(
            value=value,
            scale=scale,
            categories=categories
        )

    def parse_record(self, record: DataRecordInput, scale: ScaleStored, categories: List[ScaleCategoryStored]):
        if scale.scale_type == ScaleType.COMPLEX:
            if not record.references:
                raise ValueError("Complex scale records require at least one reference")
        record.value = self.parse_value(record.value, scale, categories)
        return record


@dataclass
class DatasetInput(DatasetBase, EnumLabeledModel):
    pass

@dataclass(eq=False)
class DatasetStored(DatasetBase, ControlledModel, ControlledAggregate):

    @property
    def controlled_models(self) -> List[ControlledModel]:
        return [self]

    @property
    def root(self) -> StoredModel:
        return self

    def model_dump(self):
        return {
            'id': self.id,
            'concept': self.concept,
            'records': [record.model_dump() for record in self.records],
            'contributors': self.contributors,
            'references': self.references
        }

    @property
    def protected(self) -> str | None:
        if self.records:
            return "Dataset with records may not be removed"
        return None

    def redacted(
            self,
            controllers: Dict[str, Dict[int, Controller]],
            user_id: int = None,
            read_teams: Set[int] = None
    ) -> 'ControlledAggregate|None':
        controller = controllers[self.label].get(self.id)
        if controller is None:
            raise ValueError(f"Controller not found for entity {self.label}: {self.id}")
        if controller.has_access(Access.READ, user_id, read_teams):
            return self

        else:
            if user_id is None:
                return None
            else:
                return replace(
                    self,
                    records = [],
                    contributors = [],
                    references = []
                )

    def to_output(self):
        return DatasetOutput(**self.model_dump())

@dataclass(eq=False)
class DatasetOutput(DatasetBase, StoredModel, EnumLabeledModel):
    id: int | None = None
