import logging

from pydantic import BaseModel

from .base import Aggregate, Entity, RecordController

from typing import List

logger = logging.getLogger(__name__)


class Person(BaseModel):
    name: str
    fullname: None|str = None

    # contact details
    email: None|str = None
    mail: None|str = None
    phone: None|str = None
    orcid: None|str = None

    description: None | str = None  # e.g. Titles etc. if not captured by Role

    user: int | None = None  # Optional ID for the corresponding user

    locations: List[int]|None = None  # references to stored Location, e.g. an Institute
    roles: List[int]|None = None  # references to PersonRole in ontology
    titles: List[int]|None = None  # references to PersonTitle in ontology

class PersonStored(Person, Entity):
    pass

class PersonRecord(Aggregate):
    person: PersonStored
    controller: RecordController

    @property
    def root(self) -> Entity:
        return self.person

    @property
    def protected(self) -> str | None:
        return None
