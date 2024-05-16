"""
Here we are seeking to describe experimental conditions/settings and exposures/treatments.
These can benefit from a similar structure to the T/M/C crop ontology specification for variables.

Conditions are "controlled" variables in an experimental context
Although the Trait concept is functionally similar here, the use is quite different.
We create the Parameter class to distinguish these.
The Plant Experimental Conditions Ontology should be referenced where possible in defining parameters

"""
from src.breedgraph.adapters.repositories.base import Entity

from src.breedgraph.domain.model.ontologies.entries import OntologyEntry
from src.breedgraph.domain.model.ontologies.variables import Subject, Method, Scale


from typing import List

class Parameter(OntologyEntry):  # akin to Variable
    # e.g. name = light level
    subjects: List[Subject] # e.g. light, substrate, air etc.

class ParameterStored(Parameter, Entity):
    pass

class Condition(OntologyEntry):
    """
    quantities/qualities that are fixed or definite throughout an experiment.
    for example:
     parameter = daylight level
     method = fluorescent tube lighting
     scale = micro-einsteins
    """
    parameter: int  # ParameterStored id
    method: int  # MethodStored id
    scale: int  # ScaleStored id

class ConditionStored(Parameter, Entity):
    pass
