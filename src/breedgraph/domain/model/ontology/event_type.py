"""
Event term from MIAPPE-64:

"An event is discrete occurrence at a particular time in the experiment
(which can be natural, such as rain, or unnatural, such as planting, watering, etc.).
Events may be the realization of Factors or parts of Factors, or may be confounding to Factors.
Can be applied at the whole study level or to only a subset of observation units per study/observation unit"
"""
from src.breedgraph.domain.model.ontology.entries import OntologyEntry

from typing import List, ClassVar

class Exposure(OntologyEntry):
    # similar to condition but must have a time/time period associated
    label: ClassVar[str] = 'Exposure'
    plural: ClassVar[str] = 'Exposures'

class EventType(OntologyEntry):
    label: ClassVar[str] = 'EventType'
    plural: ClassVar[str] = 'EventTypes'
    """
    treatments/exposures that are applied or experienced by subjects of an experiment at a particular time
    for example:
     exposure = Nitrogen
     method = N:P:K 20:10:5 (chemical)
     scale = kg/ha
     
     exposure = Fertiliser aka Nutrient
     method = N:P:K 20:10:5 (chemical) application
     scale = kg/ha
     
     exposure = water (synonym= rainfall)
     method = rainfall measurement
     scale = mm
    """

