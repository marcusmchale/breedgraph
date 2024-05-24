from src.breedgraph.domain.model.ontologies.entries import OntologyEntry

class Maintenance(OntologyEntry):
    """
        Germplasm maintenance process, e.g. Seed, Clonal
    """
    pass

class Sourcing(OntologyEntry):
    """
        Germplasm sourcing:
         - e.g. collection, mutagenesis, controlled crossing (probably many types for coffee)
    """
    pass

class Attribute(OntologyEntry):
    """
        Germplasm attribute:
         - e.g. Heat tolerant etc, QTL, etc.
    """

