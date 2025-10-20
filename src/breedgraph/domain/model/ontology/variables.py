"""
Variable ontology entries for measurement and trait variables.
Defines types of variables that can be measured in breeding experiments.

I considered the following reference in designing this model:

    Pietragalla, J.; Valette, L.; Shrestha, R.; Laporte, M.-A.; Hazekamp, T.; Arnaud, E. (2022)
    Guidelines for creating crop-specific Ontology to annotate phenotypic data: version 2.1.
    Alliance Bioversity International and CIAT. 38 p.
    https://hdl.handle.net/10568/110906

In particular the adoption of Trait/Method/Scale (T/M/S) definition for a Variable and
Terms to relate these concepts. Terms can have parent-child relationships to other terms.
T/M/S and Variable have more restricted relationships.

When entering Traits, references to the Plant Trait Ontology should be encouraged.

Note: The "Variable Status" concept from Crop Ontology is to be handled by ontology lifecycle in BreedGraph.

"""
from dataclasses import dataclass, field
from src.breedgraph.domain.model.ontology.entries import (
    OntologyEntryBase, OntologyEntryInput, OntologyEntryStored, OntologyEntryOutput
)
from src.breedgraph.domain.model.ontology.enums import ObservationMethodType, ScaleType, OntologyEntryLabel
from typing import ClassVar, List, Dict, Any


@dataclass
class TraitBase(OntologyEntryBase):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.TRAIT

    subjects: List[int] = field(default_factory=list)

@dataclass
class TraitInput(TraitBase, OntologyEntryInput):
    pass

@dataclass
class TraitStored(TraitBase, OntologyEntryStored):
    pass

@dataclass
class TraitOutput(TraitBase, OntologyEntryOutput):
    terms: List[int] = field(default_factory=list)

    variables: List[int] = field(default_factory=list)

@dataclass
class ObservationMethodBase(OntologyEntryBase):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.OBSERVATION_METHOD

    observation_type: ObservationMethodType = ObservationMethodType.MEASUREMENT

@dataclass
class ObservationMethodInput(ObservationMethodBase, OntologyEntryInput):
    pass

@dataclass
class ObservationMethodStored(ObservationMethodBase, OntologyEntryStored):
    pass

@dataclass
class ObservationMethodOutput(ObservationMethodBase, OntologyEntryOutput):
    terms: list[int] = field(default_factory=list)

    variables: list[int] = field(default_factory=list)

@dataclass
class ScaleCategoryBase(OntologyEntryBase):
    label: ClassVar[str] = OntologyEntryLabel.CATEGORY

@dataclass
class ScaleCategoryInput(ScaleCategoryBase, OntologyEntryInput):
    pass

@dataclass
class ScaleCategoryStored(ScaleCategoryBase, OntologyEntryStored):
    pass

@dataclass
class ScaleCategoryOutput(ScaleCategoryBase, OntologyEntryOutput):
    terms: list[int] = field(default_factory=list)

    scales: list[int] = field(default_factory=list)




@dataclass
class ScaleBase(OntologyEntryBase):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.SCALE

    scale_type: ScaleType = ScaleType.TEXT

@dataclass
class ScaleInput(ScaleBase, OntologyEntryInput):
    pass

@dataclass
class ScaleStored(ScaleBase, OntologyEntryStored):

    def __post_init__(self):
        self.scale_type = ScaleType(self.scale_type)

@dataclass
class ScaleOutput(ScaleBase, OntologyEntryOutput):
    terms: list[int] = field(default_factory=list)

    categories: list[int]|None = None

    variables: list[int] = field(default_factory=list)
    factors: list[int] = field(default_factory=list)

@dataclass
class VariableBase(OntologyEntryBase):  # quantities/qualities that vary and may be observed
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.VARIABLE
    # name: # CropOntology requires name to be <TraitAbbreviation>_<MethodAbbreviation >_< ScaleAbbreviation >
    # makes more sense for this format to be the abbreviation value of the OntologyEntry class
    # CropOntology variable properties has a separate label attribute to store the name

@dataclass
class VariableInput(VariableBase, OntologyEntryInput):
    pass

@dataclass
class VariableStored(VariableBase, OntologyEntryStored):
    pass

@dataclass
class VariableOutput(VariableBase, OntologyEntryOutput):
    terms: list[int] = field(default_factory=list)

    trait: int = None
    observation_method: int = None
    scale: int = None
