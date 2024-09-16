"""
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

from src.breedgraph.domain.model.ontology.entries import OntologyEntry
from typing import ClassVar

class Subject(OntologyEntry):
    label: ClassVar[str] = 'Subject'
    plural: ClassVar[str] = 'Subjects'
