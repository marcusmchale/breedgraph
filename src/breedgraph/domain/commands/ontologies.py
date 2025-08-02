from .base import Command

from typing import List

class CreateOntologyEntry(Command):
    user: int
    label: str
    name: str
    abbreviation: str|None = None
    synonyms: List[str]|None = None
    description: str | None = None
    authors: List[int]|None = None # internal person IDs
    references: List[int]|None = None # internal reference IDs
    parents: List[int]|None = None
    children: List[int]|None = None

    scale_type: str|None = None
    observation_type: str|None = None
    axes: List[str] | None = None

    categories: List[int]|None = list()
    scale: int|None = None
    rank: int|None = None
    subjects: List[int]|None = list()
    trait: int|None = None
    method: int|None = None
    condition: int|None = None
    exposure: int|None = None
