"""
Here we are seeking to describe experimental conditions/settings.
These can benefit from a similar structure to the T/M/C crop ontology specification for variables.

Conditions describe experimental setting.
Parameters require details about the control and measurement of this context.
The Plant Experimental Conditions Ontology should be referenced where possible in defining parameters

A typical case would be fixed light intensity for example.
"""
from src.breedgraph.domain.model.ontology.entries import OntologyEntry

from typing import ClassVar

class Condition(OntologyEntry):  # akin to a Trait, but is controlled/fixed for a prescribed duration
    label: ClassVar[str] = 'Condition'
    plural: ClassVar[str] = 'Conditions'

class Parameter(OntologyEntry):
    label: ClassVar[str] = 'Parameter'
    plural: ClassVar[str] = 'Parameters'
    """
    quantities/qualities that are fixed or definite throughout an experiment.
    for example:
     condition = daylight level
     method = fluorescent tube lighting
     scale = micro-einsteins
    """
