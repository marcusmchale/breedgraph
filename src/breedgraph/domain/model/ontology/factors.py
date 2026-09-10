"""
A Factor is a property whose value is established through a control or management action,
or is deliberately specified as part of the experimental design.

These can benefit from a similar structure to the T/M/C crop ontology specification for variables.

This is not quite the same as the MIAPPE definition of a factor, which is restricted to such that differentiate experimental units.
We consider this revision appropriate as we may be contrasting different experimental units in different analyses,
and as such the definition of factor would change.

Conditions describe experimental setting (e.g. light intensity) and experimental unit management, e.g. planting date.
Factors require details about the control and measurement of this context.
The Plant Experimental Conditions Ontology should be referenced where possible in defining factors

A typical case would be fixed light intensity for example.
"""
from dataclasses import dataclass, field
from breedgraph.domain.model.ontology.entries import (
    OntologyEntryBase, OntologyEntryInput, OntologyEntryStored
)
from breedgraph.domain.model.ontology.enums import ControlMethodType, OntologyEntryLabel

from typing import ClassVar

@dataclass
class ControlMethodBase(OntologyEntryBase):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.CONTROL_METHOD

    control_type: ControlMethodType = ControlMethodType.ENVIRONMENTAL

@dataclass
class ControlMethodInput(ControlMethodBase, OntologyEntryInput):
    pass

@dataclass
class ControlMethodStored(ControlMethodBase, OntologyEntryStored):
    pass


@dataclass
class ConditionBase(OntologyEntryBase):  # akin to a Trait, but is controlled/fixed for a prescribed duration
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.CONDITION

    subjects: list[int] = field(default_factory=list)

@dataclass
class ConditionInput(ConditionBase, OntologyEntryInput):
    pass

@dataclass
class ConditionStored(ConditionBase, OntologyEntryStored):
    pass

@dataclass
class FactorBase(OntologyEntryBase):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.FACTOR
    """
    quantities/qualities that are fixed or constrained for a period of time or throughout in an experiment.
    for example:
     condition = daylight level
     method = fluorescent tube lighting
     scale = micro-einsteins
    """

@dataclass
class FactorInput(FactorBase, OntologyEntryInput):
    pass

@dataclass
class FactorStored(FactorBase, OntologyEntryStored):
    pass

