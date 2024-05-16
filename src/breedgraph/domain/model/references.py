from pydantic import BaseModel
from datetime import datetime

from src.breedgraph.domain.model.people import Person

from typing import List

class Reference(BaseModel):
    name: str
    description: None|str = None
    url: None|str = None

class IdentifiedReference(Reference):
    external_id: str

class LegalReference(Reference):
    text: str = None

class LegalReferenceStored(LegalReference):
    id: int

class DataReference(Reference):
    data_format: str
    file_format: str

class DataReferenceStored(DataReference):
    id: int

class PublicationReference(Reference):
    title: str
    date: datetime
    doi: None|str
    authors: None|List[Person|str]

class PublicationStored(PublicationReference):
    id: int

class LocalFileReference(Reference):
    pass