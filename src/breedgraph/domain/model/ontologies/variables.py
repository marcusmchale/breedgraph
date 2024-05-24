"""
I considered the following reference in designing this model:

    Pietragalla, J.; Valette, L.; Shrestha, R.; Laporte, M.-A.; Hazekamp, T.; Arnaud, E. (2022)
    Guidelines for creating crop-specific Ontology to annotate phenotypic data: version 2.1.
    Alliance Bioversity International and CIAT. 38 p.
    https://hdl.handle.net/10568/110906

In particular the adoption of Trait/Method/Scale (T/M/S) definition for a Variable and
Terms to relate these concepts. Terms can have parent-child relationships to other terms.
T/M/S and Variable have more restricted relationships.

I added "Subject" to formalise descriptions of components of the system under study.
Subject is an expansion of the "entity" property described in the CropOntology.
Subject defines the entity or entities described by a trait.
    - plant structures and/or environmental components (e.g. rhizosphere)
    - developmental stage details

In considering the Planteome ontologies:

    Laurel Cooper, Justin Elser, Marie-Angelique Laporte, Elizabeth Arnaud, Pankaj Jaiswal,
    Planteome 2024 Update: Reference Ontologies and Knowledgebase for Plant Biology,
    Nucleic Acids Research, Volume 52, Issue D1, 5 January 2024, Pages D1548–D1555,
    https://doi.org/10.1093/nar/gkad1028

Most Subject descriptions are well detailed in the Plant Ontology, references to this should be encouraged.
Similarly, when entering Traits, references to the Plant Trait Ontology should be encouraged.

todo: The "Variable Status" concept from Crop Ontology is to be handled differently in BreedGraph.
    Organisation root admins should control ‘Recommended’,‘Standard',‘Obsolete’ and ‘Legacy’ annotations for variables.
    We can consider visibility of these in the future for recommendations across organisations,
    but it is most useful to resolve this at the organisation level.

"""
from enum import Enum
from src.breedgraph.domain.model.ontologies.entries import OntologyEntry

from typing import List, Set

class Trait(OntologyEntry):
    subjects: List[int]

class MethodType(str, Enum):
    MEASUREMENT = "MEASUREMENT"
    COUNTING = "COUNTING"
    ESTIMATION = "ESTIMATION"
    COMPUTATION = "COMPUTATION"
    PREDICTION = "PREDICTION"
    DESCRIPTION = "DESCRIPTION"
    CLASSIFICATION = "CLASSIFICATION"

class Method(OntologyEntry):
    type: MethodType

class ScaleType(str, Enum):
    DATE = "DATE"
    DURATION = "DURATION"
    NOMINAL = "NOMINAL"
    NUMERICAL = "NUMERICAL"
    ORDINAL = "ORDINAL"
    TEXT = "TEXT"
    CODE = "CODE"

class Category(OntologyEntry):
    pass

class Scale(OntologyEntry):
    type: ScaleType
    categories: List[int] = list()  # category ontology entry references

class Variable(OntologyEntry):  # quantities/qualities that vary and may be observed
    trait: int  # OntologyEntry id
    method: int  # OntologyEntry id
    scale: int  # OntologyEntry id
    # name: # CropOntology requires name to be <TraitAbbreviation>_<MethodAbbreviation >_< ScaleAbbreviation >
    # makes more sense for this format to be the abbreviation value of the OntologyEntry class
    # CropOntology variable properties has a separate label attribute to store the name
