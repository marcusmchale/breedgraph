from dataclasses import dataclass, field, replace
from abc import ABC
from typing import List, ClassVar, Set, Dict, Self
from numpy import datetime64

from src.breedgraph.service_layer.tracking.wrappers import asdict
from src.breedgraph.domain.model.base import LabeledModel, StoredModel
from src.breedgraph.domain.model.controls import ControlledModel, ControlledAggregate, Access, ReadRelease, Controller

@dataclass
class DataRecordBase(ABC):
    label: ClassVar[str] = 'Record'
    plural: ClassVar[str] = 'Records'

    unit: int|None = None
    value: str|None = None

    # time and/or start and/or end time to describe period of relevance for the record.
    time: datetime64|None = None
    start: datetime64|None = None
    end: datetime64|None = None

    references: List[int]|None = field(default_factory=list)
    # to link supporting data in references repository
    # e.g. raw data or another repository with supporting data

@dataclass
class DataRecordInput(DataRecordBase, LabeledModel):
    pass

@dataclass
class DataRecordStored(DataRecordBase, ControlledModel):
    submitted: datetime64|None = None

    def redacted(self, controller: Controller, user_id=None, read_teams=None) -> Self:
        if controller.has_access(Access.READ, user_id, read_teams):
            return self
        else:
            return replace(
                self,
                value = self.value and self.redacted_str,
            )

@dataclass
class DataRecordOutput(DataRecordBase, LabeledModel):
    submitted: datetime64|None = None


@dataclass(eq=False)
class DataSetBase(ABC):
    """
        DataRecords are aggregated per ontology_id into a DataSet.
        Typically, a dataset will be referenced by a single study,
        though multiple studies may reference a common dataset.

        "ontology_id" should reference to Variable or Factor in the ontology.
        "Records" is a list of DataRecord
        """
    label: ClassVar[str] = 'DataSet'
    plural: ClassVar[str] = 'DataSets'

    concept: int = None
    records: List[DataRecordStored|DataRecordInput] = field(default_factory=list)

    contributors: List[int] = field(default_factory=list) # PersonStored that contributed to this dataset by ID
    references: List[int] = field(default_factory=list) # to link supporting data in references repository
    # e.g. raw data or another repository with supporting data

    def add_record(self, record: DataRecordInput):
        self.records.append(record)

    def model_dump(self):
        dump = asdict(self)
        dump['records'] = [record.model_dump() for record in self.records]
        return dump

@dataclass
class DataSetInput(DataSetBase, LabeledModel):
    pass

@dataclass(eq=False)
class DataSetStored(DataSetBase, ControlledModel, ControlledAggregate):

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
            return "DataSet with records may not be removed"
        return None

    def redacted(
            self,
            controllers: Dict[str, Dict[int, Controller]],
            user_id: int = None,
            read_teams: Set[int] = None
    ) -> 'ControlledAggregate|None':

        controller = controllers[self.label][self.id]
        if controller.has_access(Access.READ, user_id, read_teams):
            return self

        else:
            if user_id is None:
                return None
            else:
                return replace(
                    self,
                    records = [
                        record.redacted(controllers[record.label][record.id], user_id, read_teams)
                        if isinstance(record, DataRecordStored) else record
                        for record in self.records
                    ],
                    contributors = list(),
                    references = list()
                )

    def to_output(self):
        return DataSetOutput(**self.model_dump())

@dataclass(eq=False)
class DataSetOutput(DataSetBase):
    id: int | None = None
