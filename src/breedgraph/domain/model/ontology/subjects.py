"""
Subject ontology entries for experimental subjects and observation units.
Defines types of subjects that can be observed in breeding experiments.

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
"""
from dataclasses import dataclass, field
from src.breedgraph.domain.model.ontology.entries import (
    OntologyEntryBase, OntologyEntryInput, OntologyEntryStored, OntologyEntryOutput
)
from typing import ClassVar

@dataclass
class SubjectBase(OntologyEntryBase):
    label: ClassVar[str] = 'Subject'
    plural: ClassVar[str] = 'Subjects'

@dataclass
class SubjectInput(SubjectBase, OntologyEntryInput):
    pass

@dataclass
class SubjectStored(SubjectBase, OntologyEntryStored):
    pass

@dataclass
class SubjectOutput(SubjectBase, OntologyEntryOutput):
    terms: list[int] = field(default_factory=list)

    traits: list[int] = field(default_factory=list)
    conditions: list[int] = field(default_factory=list)