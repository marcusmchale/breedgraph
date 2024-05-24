"""

For treatments/exposures we use the Events term from BrAPI Phenotyping,
We encode eventType becomes as a stored "Treatment" which should also be used for exposures.

"""
from src.breedgraph.domain.model.ontologies.entries import OntologyEntry

from typing import List

class Exposure(OntologyEntry):
    # e.g. fertiliser application, rainfall etc.
    subjects: List[int]  # e.g. substrate, soil, air, etc.

class Event(OntologyEntry):
    """
    treatments/exposures that are applied or experienced by subjects of an experiment
    for example:
     treatment = fertliser application
     method = N:P:K 20:10:5 (chemical)
     scale = kg/ha
    """
    exposure: int
    method: int
    scale: int
