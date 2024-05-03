from enum import Enum

class ScientificType(str, Enum):
    GENOTYPE = 'GENOTYPE'
    PHENOTYPE = 'PHENOTYPE'
    ENVIRONMENT = 'ENVIRONMENT'
