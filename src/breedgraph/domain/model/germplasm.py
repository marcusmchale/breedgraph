from pydantic import BaseModel

from src.breedgraph.domain.model.time_descriptors import TimeDescriptor
from src.breedgraph.adapters.repositories.base import Entity

from typing import List

class Germplasm(BaseModel):
    """
    Germplasm should form a graph relating entries
    Parents and children can describe relationships, with sourcing ,

    These may include:
        crops, e.g. coffee
        species, e.g. arabica, robusta etc.
        cultivars, e.g. Caturra, Geisha
        landraces, e.g. YirgaChefe
            - note we are not storing location information specifically in the ontology
              but this detail can be added in the description or references
        hybrids, e.g. Centramericano (H1)
        etc.


    for example, sourcing, phylogeny. Details of these relationships can be outlined in the description.

    e.g. Coffee <- Coffea arabica <- Marsellesa <- Centroamericano -> MSH12 ...
    """

    name: str
    synonyms: List[str] = list()
    description: str

    maintenance: int|None = None  # ontology reference for MaintenanceStored
    sourcing: int|None = None  # ontology reference for SourcingStored

    attributes: List[int]  # ontology references for attributes

    references: List[int] = list()  # internal reference ID

    parents: List[int] = list()  # ontology entry IDs, to be stored with related_to towards parent
    children: List[int] = list()  # ontology entry IDs, to be stored with related_to towards self


class GermplasmStored(Germplasm, Entity):
    pass


class Accession(Germplasm):
    # these are optional for Germplasm but required for accession
    maintenance: int # ontology reference for MaintenanceStored
    sourcing: int # ontology reference for SourcingStored

    location: int  # LocationStored ID where this accession was sourced
    time: TimeDescriptor  # When this accession was sourced
    """
    Germplasm that was collected at one time from a single source
    Either a location at a time OR another accession(s)
        - e.g. a hybrid between two accessions
        - e.g. a mutant from a single accession
        - e.g. a seed lot obtained from another accession

    Ideally location and time are still recorded for sourcing from another accession

    Likely to still represent a population, but must have recorded history of sourcing and maintenance.
    Details about the maintenance of the accession should be included in the description.

    The root of an accession hierarchy should have at least one Germplasm from the ontology in its parents

    May have varieties as children where tracking of specific sourcing has been lost

    Best case scenario is accessions are managed in controlled lots.
    each lot recorded as a new accession, children of the parent accession.
    Each time the provenance should be recorded (place/time collected/generated etc.).
    """

class AccessionStored(Accession, Entity):
    pass