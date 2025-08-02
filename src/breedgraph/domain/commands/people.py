from .base import Command

from typing import List

class CreatePerson(Command):
    submitting_user: int

    name: str
    fullname: None|str = None

    # contact details
    email: None|str = None
    mail: None|str = None
    phone: None|str = None
    orcid: None|str = None

    description: None | str = None

    user: int|None = None
    teams: List[int]|None = None
    locations: List[int]|None = None
    roles: List[int]|None = None
    titles: List[int]|None = None


class UpdatePerson(Command):
    submitting_user: int
    person_id: int

    name: str|None = None
    fullname: None | str = None
    # contact details
    email: None|str = None
    mail: None|str = None
    phone: None|str = None
    orcid: None|str = None

    description: None | str = None

    user: int|None = None
    teams: List[int]|None = None
    locations: List[int]|None = None
    roles: List[int]|None = None
    titles: List[int]|None = None


class DeletePerson(Command):
    submitting_user: int
    person_id: int
