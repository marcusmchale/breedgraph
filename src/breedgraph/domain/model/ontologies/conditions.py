"""
Here we are seeking to describe experimental conditions/settings and exposures/treatments.
These can benefit from a similar structure to the T/M/C crop ontology specification for variables.

Conditions are "controlled" variables in an experimental context
Although the Trait concept is functionally similar here, the use is quite different.
We create the Parameter class to distinguish these.
The Plant Experimental Conditions Ontology should be referenced where possible in defining parameters

"""
from src.breedgraph.domain.model.ontologies.entries import OntologyEntry

from typing import List, Set, ClassVar

class Condition(OntologyEntry):  # akin to a Trait, but is controlled/fixed for a prescribed duration
    # e.g. name = light level
    subjects: List[int] # e.g. light, substrate, air etc.

class Parameter(OntologyEntry):
    """
    quantities/qualities that are fixed or definite throughout an experiment.
    for example:
     condition = daylight level
     method = fluorescent tube lighting
     scale = micro-einsteins
    """
    condition: int  # Condition id
    method: int  # Method id
    scale: int  # Scale id
