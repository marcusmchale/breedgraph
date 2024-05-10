"""
Here we are seeking to describe experimental conditions/settings and exposures/treatments.
These can benefit from a similar structure to the T/M/C crop ontology specification for variables.

Conditions are "controlled" variables in an experimental context
Although the Trait concept is functionally similar here, the use is quite different.
We create the Parameter class to distinguish these.
The Plant Experimental Conditions Ontology should be referenced where possible in defining parameters

For treatments/exposures we use the Events term from BrAPI Phenotyping,
We encode eventType becomes as a stored "Treatment" which should also be used for exposures.

"""
from src.breedgraph.adapters.repositories.base import Entity

from src.breedgraph.domain.model.ontologies.entries import OntologyEntry
from src.breedgraph.domain.model.ontologies.variables import SubjectType

from typing import List

class Parameter(OntologyEntry):  # akin to Variable
    subjects: List[SubjectType]

class ParameterStored(Parameter, Entity):
    pass

class Condition(OntologyEntry):  # quantities/qualities that are fixed or definite throughout an experiment.
    parameter: int  # ParameterStored id
    method: int  # MethodStored id
    scale: int  # ScaleStored id

class ConditionStored(Parameter, Entity):
    pass

class Treatment(OntologyEntry): #a.k.a. exposure
    subjects: List[SubjectType]

class Event(OntologyEntry):
    treatment: int
    method: int
    scale: int
