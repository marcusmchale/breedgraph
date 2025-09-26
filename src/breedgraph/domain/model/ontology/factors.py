"""
Here we are seeking to describe experimental conditions/settings.
These can benefit from a similar structure to the T/M/C crop ontology specification for variables.

This is not quite the same as the MIAPPE definition of a factor, which is restricted to such that differentiate experimental units.
We consider this revision appropriate as we may be contrasting different experimental units in different analyses,
and as such the definition of factor would change.

Conditions describe experimental setting.
Factors require details about the control and measurement of this context.
The Plant Experimental Conditions Ontology should be referenced where possible in defining factors

A typical case would be fixed light intensity for example.
"""
from dataclasses import dataclass, field
from src.breedgraph.domain.model.ontology.entries import (
    OntologyEntryBase, OntologyEntryInput, OntologyEntryStored, OntologyEntryOutput
)
from src.breedgraph.domain.model.ontology.enums import ControlMethodType, OntologyEntryLabel

from typing import ClassVar

@dataclass
class ControlMethodBase(OntologyEntryBase):
    # Unlike observation methods, control methods do not have a method_type
    label: ClassVar[str] = OntologyEntryLabel.CONTROL_METHOD

    control_type: ControlMethodType = ControlMethodType.ENVIRONMENTAL

@dataclass
class ControlMethodInput(ControlMethodBase, OntologyEntryInput):
    pass

@dataclass
class ControlMethodStored(ControlMethodBase, OntologyEntryStored):
    pass

@dataclass
class ControlMethodOutput(ControlMethodBase, OntologyEntryOutput):
    terms: list[int] = field(default_factory=list)
    factors: list[int] = field(default_factory=list)

@dataclass
class ConditionBase(OntologyEntryBase):  # akin to a Trait, but is controlled/fixed for a prescribed duration
    label: ClassVar[str] = OntologyEntryLabel.CONDITION

    subjects: list[int] = field(default_factory=list)

@dataclass
class ConditionInput(ConditionBase, OntologyEntryInput):
    pass

@dataclass
class ConditionStored(ConditionBase, OntologyEntryStored):
    pass

@dataclass
class ConditionOutput(ConditionBase, OntologyEntryOutput):
    terms: list[int] = field(default_factory=list)

    factors: list[int] = field(default_factory=list)

@dataclass
class FactorBase(OntologyEntryBase):
    label: ClassVar[str] = OntologyEntryLabel.FACTOR
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

@dataclass
class FactorOutput(FactorBase, OntologyEntryOutput):
    terms: list[int] = field(default_factory=list)

    condition: int = None
    control_method: int = None
    scale: int = None