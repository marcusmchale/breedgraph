from pydantic import BaseModel, Field, computed_field
from abc import ABC, abstractmethod

class Entity(BaseModel):
    id: int = Field(frozen=True)

    def __hash__(self):
        return hash(self.id)

from typing import List
from src.breedgraph.domain.events.accounts import Event

class Aggregate(ABC, BaseModel):
    events: List[Event] = list()

    @property
    @abstractmethod
    def root(self) -> Entity:
        raise NotImplementedError

    @property
    @abstractmethod
    def protected(self) -> str|None:
        # Return a string describing why this aggregate is protected
        # or None/empty string if safe to delete
        raise NotImplementedError

    def __hash__(self) -> int:
        return hash(self.root)