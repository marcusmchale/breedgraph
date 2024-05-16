"""

For treatments/exposures we use the Events term from BrAPI Phenotyping,
We encode eventType becomes as a stored "Treatment" which should also be used for exposures.

"""
from src.breedgraph.adapters.repositories.base import Entity, Aggregate

from src.breedgraph.domain.model.ontologies.entries import OntologyEntry
from src.breedgraph.domain.model.ontologies.conditions import Subject

from typing import List

class Exposure(OntologyEntry): #a.k.a. Treatment
    # e.g. fertiliser application
    subjects: List[Subject]  # e.g. substrate, soil, air, etc.

class ExposureStored(Exposure, Entity):
    pass

class EventType(OntologyEntry):
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

class EventTypeStored(EventType, Entity):
    pass
