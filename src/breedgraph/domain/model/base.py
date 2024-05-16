from pydantic import BaseModel, Field
from abc import ABC, abstractmethod

class Entity(BaseModel):
    id: int = Field(frozen=True)

class Aggregate(BaseModel, ABC):

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

    def __hash__(self):
        return hash(self.root.id)