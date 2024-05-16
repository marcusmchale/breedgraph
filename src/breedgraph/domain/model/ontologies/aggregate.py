from pydantic import Field, computed_field

from src.breedgraph.adapters.repositories.base import Entity, Aggregate
from src.breedgraph.domain.model.references import LegalReferenceStored

from .entries import Version, VersionStored, OntologyEntry, OntologyEntryStored, Term, TermStored
from .subjects import Subject, SubjectStored

from .variables import Trait, TraitStored, Method, MethodStored, Scale, ScaleStored, Variable, VariableStored
from .conditions import Parameter, ParameterStored, Condition, ConditionStored
from .events import Exposure, ExposureStored, EventType, EventTypeStored

from .germplasm import Sourcing, SourcingStored, Maintenance, MaintenanceStored, Attribute, AttributeStored

from .facilities import FacilityType, FacilityTypeStored
from .locations import LocationType, LocationTypeStored
from .designs import Design, DesignStored
from .layout import LayoutType, LayoutTypeStored

from typing import List


class Ontology(Aggregate):
    version: Version|VersionStored

    licence: int | None = None  # id for internally stored LegalReference
    copyright: int|None = None  # id for internally stored LegalReference

    terms: List[Term|TermStored]
    subjects: List[Subject|SubjectStored]

    traits: List[Trait|TraitStored]
    parameters: List[Parameter | ParameterStored]
    exposures: List[Exposure|ExposureStored]

    methods: List[Method|MethodStored]
    scales: List[Scale|ScaleStored]

    variables: List[Variable|VariableStored]

    conditions: List[Condition|ConditionStored]
    exposures: List[Exposure|ExposureStored]
    events: List[EventType | EventTypeStored]

    # germplasm attributes
    sourcing: List[Sourcing|SourcingStored]
    maintenance: List[Maintenance|MaintenanceStored]
    attributes: List[Attribute|AttributeStored]

    locations: List[LocationType|LocationTypeStored]
    facilities: List[FacilityType|FacilityTypeStored]
    layouts: List[LayoutType|LayoutTypeStored]

    designs: List[Design|DesignStored]


    @computed_field
    @property
    def root(self) -> Entity:
        return self.version

    @property
    def protected(self) -> [str|bool]:
        if isinstance(self.version, VersionStored):
            return "Stored ontology is protected"
        else:
            return False
