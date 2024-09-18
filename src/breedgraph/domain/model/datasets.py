from typing import List, ClassVar, Set

from pydantic import Field
from numpy import datetime64
from src.breedgraph.domain.model.base import LabeledModel, StoredModel
from src.breedgraph.domain.model.time_descriptors import PyDT64
from src.breedgraph.domain.model.controls import ControlledModel, ControlledAggregate, Access


class DataRecordBase(LabeledModel):
    label: ClassVar[str] = 'Record'
    plural: ClassVar[str] = 'Records'

    value: str | int | float | None

    # Start and/or end time to describe period of relevance for the record.
    start: PyDT64 | None = None
    end: PyDT64 | None = None

    references: List[int] = list()
    # to link supporting data in references repository
    # e.g. raw data or another repository with supporting data


class DataRecordInput(DataRecordBase):
    pass

class DataRecordStored(DataRecordBase, StoredModel):
    submitted: PyDT64 = Field(frozen=True)

class DataSetBase(LabeledModel):
    """
        DataRecords are aggregated per term into a DataSet.
        Typically, a dataset will be referenced by a single study,
        though multiple studies may reference a common dataset.

        "Term" is a reference to Variable, EventType or Parameter in the ontology.
        "Unit_Records" is a map keyed by "Unit" ID (see blocks repository) with values of DataRecord
        """
    label: ClassVar[str] = 'DataSet'
    plural: ClassVar[str] = 'DataSets'

    term: int
    unit_records: dict[int, List[DataRecordStored|DataRecordInput]] = dict()

    contributors: List[int] = list() # PersonStored that contributed to this dataset by ID
    references: List[int] = list() # to link supporting data in references repository
    # e.g. raw data or another repository with supporting data

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
        for unit, records in self.unit_records.items():
            if records:
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
                redacted = self.model_copy(deep=True)
                for key, value in redacted.unit_records.items():
                    for record in value:
                        record.value = self.redacted_str if record.value is not None else None
                        record.start = None
                        record.end = None
                        record.data = []
                        record.people = []

                return redacted
