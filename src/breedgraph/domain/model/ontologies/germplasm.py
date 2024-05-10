from pydantic import BaseModel, field_validator

from src.breedgraph.domain.model.ontologies.entries import OntologyEntry
from src.breedgraph.adapters.repositories.base import Entity

from src.breedgraph.domain.model.time_descriptors import TimeDescriptor

from typing import List

# similar to
class Germplasm(OntologyEntry):
    pass

class Variety(Germplasm):
    """
    Variety entries should form a graph relating "variety" labels
    by recorded or even presumed relationships of inheritance.

    Variety entries may include:
        crops, e.g. coffee
        species, e.g. arabica, robusta etc.
        cultivars, e.g. Caturra, Geisha
        landraces, e.g. YirgaChefe
            - note we are not storing location information specifically in the ontology
              but this detail can be added in the description or references
        hybrids, e.g. Centramericano (H1)
        etc.

    Parents and children should describe pseudo-pedigrees.

    e.g. Coffee <- Coffea arabica <- Marsellesa <- Centroamericano -> MSH12 ...
    """
    pass

class VarietyStored(Variety, Entity):
    pass

class GermplasmSourceMode(OntologyEntry):
    """
    Used to describe way an accession was sourced
    e.g.
        - Collected from the wild
        - Controlled cross,
        - Selected from a segregating population,
        - genetic transformation,
        - mutation etc.
    """

class GermplasmSourceModeStored(GermplasmSourceMode, Entity):
    pass

class Source(BaseModel):
    location: int  # stored location ID
    time: TimeDescriptor
    mode: GermplasmSourceMode

class Accession(Germplasm):
    """
    Germplasm collected at one time from a single source (location/population)
      OR derived directly from other accession(s)
        - e.g. a hybrid between two accessions
        - e.g. a mutant from a single accession
        - e.g. a seed lot obtained from another accession

    Likely to still represent a population, but must have recorded history of maintenance
    Details about the maintenance of the accession should be included in the description

    The root of an accession hierarchy should have at least one Variety in its parents

    May have varieties as children where tracking of specific sourcing has been lost

    Best case scenario is accessions are managed in controlled lots.
    each lot recorded as a new accession, children of the parent accession.
    Each time the provenance should be recorded (place/time collected/generated etc.).
    """
    source: Source

class AccessionStored(Accession, Entity):
    pass
