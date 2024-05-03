import logging

from enum import Enum
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class PersonRole(BaseModel):
    name: str
    description: str


class Person(BaseModel):
    name: str
    fullname: None|str = None

    description: None | str = None
    role: None | PersonRole = None
    institute: None | str = None

    email: None|str = None
    mail: None|str = None
    phone: None|str = None
    orcid: None|str = None

class PersonStored(BaseModel):
    id: int
    user: None|int = None  # ID for the corresponding user if they are registered
