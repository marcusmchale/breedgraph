from pydantic import BaseModel, Field, computed_field
from abc import ABC, abstractmethod
from enum import IntEnum
from datetime import datetime

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
        return hash(self.root.id)

class Release(IntEnum):
    PRIVATE = 0  # accessible only to users with an authorised affiliation to the controller
    REGISTERED = 1 # accessible to any registered user
    PUBLIC = 2  # accessible to non-registered users # todo


class Control(BaseModel):
    team: int  # team id
    release: Release
    time: datetime

class WriteStamp(BaseModel):
    user: int  # user id
    time: datetime

class RecordController(BaseModel):
    controls: List[Control]
    writes: List[WriteStamp] = Field(frozen=True) # for auditing

    @property
    def controllers(self):
        return [c.team for c in self.controls]

    @property
    def release(self):
        return min([c.release for c in self.controls])

    @property
    def created(self):
        return min([w.time for w in self.writes])

    @property
    def updated(self):
        return max([w.time for w in self.writes])


