"""
An event is the confluence of multiple factors and variables at a time or for a period of time.

This differs from the Event term from MIAPPE-64:
"An event is discrete occurrence at a particular time in the experiment
(which can be natural, such as rain, or unnatural, such as planting, watering, etc.).
Events may be the realization of Factors or parts of Factors, or may be confounding to Factors.
Can be applied at the whole study level or to only a subset of observation units per study/observation unit"

In particular we do not use the same meaning of Factor, see notes on that page.
Given this, and our hierarchical subject structure, Events are applied to subjects.
"""

from dataclasses import dataclass, field
from src.breedgraph.domain.model.ontology.entries import (
    OntologyEntryBase, OntologyEntryInput, OntologyEntryStored, OntologyEntryOutput
)
from src.breedgraph.domain.model.ontology.enums import OntologyEntryLabel

from typing import List, ClassVar


@dataclass
class EventTypeBase(OntologyEntryBase):
    label: ClassVar[str] = OntologyEntryLabel.EVENT
    """
    The EventType may have multiple variables and/or factors associated with it.
    """

@dataclass
class EventTypeInput(EventTypeBase, OntologyEntryInput):
    pass

@dataclass
class EventTypeStored(EventTypeBase, OntologyEntryStored):
    pass

@dataclass
class EventTypeOutput(EventTypeBase, OntologyEntryOutput):
    terms: List[int] = field(default_factory=list)

    factors: int = None
    variables: int = None