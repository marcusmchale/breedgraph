from .base import Command

from typing import List

class AddTerm(Command):
    user: int

    name: str

    description: str|None = None
    abbreviation: str|None = None
    synonyms: List[str]|None = None

    authors: List[int]|None = None # internal person IDs
    references: List[int]|None = None # internal reference IDs
    parents: List[int]|None = None