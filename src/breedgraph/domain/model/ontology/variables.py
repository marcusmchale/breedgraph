"""
I considered the following reference in designing this model:

    Pietragalla, J.; Valette, L.; Shrestha, R.; Laporte, M.-A.; Hazekamp, T.; Arnaud, E. (2022)
    Guidelines for creating crop-specific Ontology to annotate phenotypic data: version 2.1.
    Alliance Bioversity International and CIAT. 38 p.
    https://hdl.handle.net/10568/110906

In particular the adoption of Trait/Method/Scale (T/M/S) definition for a Variable and
Terms to relate these concepts. Terms can have parent-child relationships to other terms.
T/M/S and Variable have more restricted relationships.

When entering Traits, references to the Plant Trait Ontology should be encouraged.

Note: The "Variable Status" concept from Crop Ontology is to be handled by ontology versioning in BreedGraph.

"""
from src.breedgraph.domain.model.ontology.entries import OntologyEntry, ObservationMethodType, ScaleType
from typing import ClassVar

class Trait(OntologyEntry):
    label: ClassVar[str] = 'Trait'
    plural: ClassVar[str] = 'Traits'


class ObservationMethod(OntologyEntry):
    label: ClassVar[str] = 'ObservationMethod'
    plural: ClassVar[str] = 'ObservationMethods'
    observation_type: ObservationMethodType

class ScaleCategory(OntologyEntry):
    label: ClassVar[str] = 'ScaleCategory'
    plural: ClassVar[str] = 'ScaleCategories'

class Scale(OntologyEntry):
    label: ClassVar[str] = 'Scale'
    plural: ClassVar[str] = 'Scales'
    scale_type: ScaleType

class Variable(OntologyEntry):  # quantities/qualities that vary and may be observed
    label: ClassVar[str] = 'Variable'
    plural: ClassVar[str] = 'Variables'
    # name: # CropOntology requires name to be <TraitAbbreviation>_<MethodAbbreviation >_< ScaleAbbreviation >
    # makes more sense for this format to be the abbreviation value of the OntologyEntry class
    # CropOntology variable properties has a separate label attribute to store the name
