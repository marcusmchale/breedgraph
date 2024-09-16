from typing import List, ClassVar, Set

from pydantic import Field

from src.breedgraph.domain.model.base import LabeledModel, StoredModel
from src.breedgraph.domain.model.references import (
    DataFileInput, DataFileStored,
    DataExternalInput, DataExternalStored
)
from src.breedgraph.domain.model.time_descriptors import PyDT64
from src.breedgraph.domain.model.controls import ControlledModel, ControlledAggregate, Access


class Record(LabeledModel):
    label: ClassVar[str] = 'Record'
    plural: ClassVar[str] = 'Records'

    value: str | int | float | None

    # Start and/or end time to describe period of relevance for the record.
    start: PyDT64 | None = None
    end: PyDT64 | None = None

    data: List[DataFileInput|DataFileStored|DataExternalInput|DataExternalStored] = list()
    # to link supporting data, e.g. raw data

    people: List[int]  # reference to PersonStored that are responsible for this record.


class StudyTerm(ControlledModel, ControlledAggregate):
    """
    Records are aggregated per term, per study.

    Term is a reference to Variable, EventType or Parameter in the ontology.

    Grouping according to study is most appropriate for access control and
    to ensure consistency and avoid duplication in data mergers.

    The records map is keyed by Unit ID (units are aggregated into blocks)

    Terminology to consider for other abstractions:
    observations (for a variable),
    event instances (for an event type)
    or parameter levels (for a parameter).
    """
    label: ClassVar[str] = 'StudyTerm'
    plural: ClassVar[str] = 'StudyTerms'

    study: int = Field(frozen=True) # reference to Study
    term: int = Field(frozen=True) # reference to Variable/Parameter/EventType in ontology

    records: dict[int, List[Record]]
    # key in records is unit ID

    @property
    def controlled_models(self) -> List[ControlledModel]:
        return [self]

    @property
    def root(self) -> StoredModel:
        return self

    @property
    def protected(self) -> str | None:
        for key, value in self.records.items():
            if value:
                return "StudyTerm with records may not be removed"

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
                for key, value in redacted.records.items():
                    for record in value:
                        record.value = self.redacted_str if record.value is not None else None
                        record.start = None
                        record.end = None
                        record.data = []
                        record.people = []

                return redacted
