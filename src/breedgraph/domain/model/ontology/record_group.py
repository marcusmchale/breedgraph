"""
A record group is a set of records associated by a common criterion arising from
 the execution, observation, processing, or organization of a study.

The ontology should describe reusable types of record groups
that can be referenced in study definitions and ultimately the record group data.

"""
from dataclasses import dataclass
from breedgraph.domain.model.ontology.entries import (
    OntologyEntryBase, OntologyEntryInput, OntologyEntryStored
)
from breedgraph.domain.model.ontology.enums import OntologyEntryLabel, RecordGroupExtent
from typing import ClassVar

@dataclass
class RecordGroupTypeBase(OntologyEntryBase):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.RECORD_GROUP_TYPE

    extent: RecordGroupExtent | None = None  # required, see RecordGroupExtent

    def __post_init__(self):
        if self.extent is None:
            raise ValueError("A record group type requires an extent")

@dataclass
class RecordGroupTypeInput(RecordGroupTypeBase, OntologyEntryInput):
    pass

@dataclass
class RecordGroupTypeStored(RecordGroupTypeBase, OntologyEntryStored):
    pass
