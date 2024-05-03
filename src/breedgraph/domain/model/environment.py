from pydantic import BaseModel, field_validator

from src.breedgraph.domain.model.references import Reference
from src.breedgraph.domain.model.ontologies import Ontology

class Season(BaseModel):
    name: str
    year: int  # 4 digit

    @field_validator('year')
    def validate_year(cls, v):
        if not len(str(v)) == 4:
            raise ValueError('Year must be 4 digits')

class SeasonStored(Season):
    id: int

class EnvironmentUnit(BaseModel):
    name: str
    description: str = None
    ontology: Ontology = None

    value_type: int|float|str
    symbol: str = None

class EnvironmentUnitStored(EnvironmentUnit):
    id: int

class EnvironmentValue(BaseModel):
    value: int|str|float
    description: str = None
    ontology: Ontology = None

class EnvironmentValueStored(EnvironmentValue):
    id: int

class EnvironmentParameter(BaseModel):
    name: str
    description: None|str = None
    ontology: None|Ontology = None

    unit: EnvironmentUnit
    value: EnvironmentValue

    @field_validator('value')
    def validate_value(cls, input_value, values):
        assert isinstance(input_value.value, values.unit.value_type)


