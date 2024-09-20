from .base import Command

from typing import List

class AddOntologyEntry(Command):
    user: int
    name: str
    abbreviation: str|None = None
    synonyms: List[str]|None = None
    description: str | None = None
    authors: List[int]|None = None # internal person IDs
    references: List[int]|None = None # internal reference IDs
    parents: List[int]|None = None
    children: List[int]|None = None

class AddTerm(AddOntologyEntry):
    pass

class AddSubject(AddOntologyEntry):
    pass

class AddLocationType(AddOntologyEntry):
    pass

class AddLayoutType(AddOntologyEntry):
    pass

class AddDesignType(AddOntologyEntry):
    pass

class AddRole(AddOntologyEntry):
    pass

class AddTitle(AddOntologyEntry):
    pass

class AddGermplasmMethod(AddOntologyEntry):
    pass

class AddObservationMethod(AddOntologyEntry):
    method_type: str

class AddScale(AddOntologyEntry):
    scale_type: str
    categories: List[int] = list()

class AddCategory(AddOntologyEntry):
    scale: int
    rank: int

class AddTrait(AddOntologyEntry):
    subjects: List[int]

class AddVariable(AddOntologyEntry):
    trait: int
    method: int
    scale: int

class AddCondition(AddOntologyEntry):
    pass

class AddParameter(AddOntologyEntry):
    condition: int
    method: int
    scale: int

class AddExposure(AddOntologyEntry):
    pass

class AddEvent(AddOntologyEntry):
    exposure: int
    method: int
    scale: int
