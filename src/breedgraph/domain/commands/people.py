from .base import Command

from typing import List

class AddPerson(Command):

    submitting_user: int

    name: str
    fullname: None|str = None

    # contact details
    email: None|str = None
    mail: None|str = None
    phone: None|str = None
    orcid: None|str = None

    description: None | str = None  # e.g. Titles etc. if not captured by Role

    user: int|None = None # reference to stored User
    locations: List[int]|None = None  # references to stored Location, e.g. an Institute
    roles: List[int]|None = None  # references to PersonRole in ontology
    titles: List[int]|None = None  # references to PersonTitle in ontology
