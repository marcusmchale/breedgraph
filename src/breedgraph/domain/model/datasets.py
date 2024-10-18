from typing import List, ClassVar, Set

from pydantic import Field
from src.breedgraph.domain.model.base import LabeledModel, StoredModel
from src.breedgraph.domain.model.time_descriptors import PyDT64
from src.breedgraph.domain.model.controls import ControlledModel, ControlledAggregate, Access, ReadRelease


class DataRecordBase(LabeledModel):
    label: ClassVar[str] = 'Record'
    plural: ClassVar[str] = 'Records'

    unit: int
    value: str | None

    # Start and/or end time to describe period of relevance for the record.
    start: PyDT64 | None = None
    end: PyDT64 | None = None

    references: List[int]|None = list()
    # to link supporting data in references repository
    # e.g. raw data or another repository with supporting data


class DataRecordInput(DataRecordBase):
    pass

class DataRecordStored(DataRecordBase, StoredModel):
    submitted: PyDT64 = Field(frozen=True)

class DataRecordOutput(DataRecordBase):
    submitted: PyDT64

class DataSetBase(LabeledModel):
    """
        DataRecords are aggregated per term into a DataSet.
        Typically, a dataset will be referenced by a single study,
        though multiple studies may reference a common dataset.

        "Term" is a reference to Variable, EventType or Parameter in the ontology.
        "Records" is a list of DataRecord
        """
    label: ClassVar[str] = 'DataSet'
    plural: ClassVar[str] = 'DataSets'

    term: int
    records: List[DataRecordStored|DataRecordInput] = list()

    contributors: List[int] = list() # PersonStored that contributed to this dataset by ID
    references: List[int] = list() # to link supporting data in references repository
    # e.g. raw data or another repository with supporting data

    def add_record(self, record: DataRecordInput):
        self.records.append(record)

class DataSetInput(DataSetBase):
    pass

class DataSetStored(DataSetBase, ControlledModel, ControlledAggregate):

    @property
    def controlled_models(self) -> List[ControlledModel]:
        return [self]

    @property
    def root(self) -> StoredModel:
        return self

    @property
    def protected(self) -> str | None:
        if self.records:
            return "DataSet with records may not be removed"

    def redacted(self, user_id: int = None, read_teams: Set[int] = None) -> 'ControlledAggregate|None':
        if read_teams is None:
            read_teams = set()

        if self.controller.has_access(Access.READ, user_id, read_teams):
            return self

        else:
            if user_id is None:
                return None
            else:
                redacted = self.model_copy(
                    deep=True,
                    update={'records': list(), 'contributors': list(), 'references': list()}
                )
                return redacted

    def to_output(self):
        return DataSetOutput(**self.model_dump(), release=self.controller.release)

class DataSetOutput(DataSetBase):
    id: int
    release: ReadRelease
