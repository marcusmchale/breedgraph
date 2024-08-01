from abc import ABC, abstractmethod
from pydantic import BaseModel, RootModel, Field, ValidationError, ValidationInfo, field_validator, SerializeAsAny
from enum import IntEnum
from datetime import datetime
from neo4j.time import DateTime as Neo4jDateTime

from typing import Dict, List, Callable, Any, ClassVar, Set

from src.breedgraph.domain.model.accounts import AccountStored
from src.breedgraph.domain.model.organisations import Access
from src.breedgraph.domain.model.base import Aggregate
from src.breedgraph.custom_exceptions import UnauthorisedOperationError
from src.breedgraph.adapters.repositories.trackable_wrappers import TrackedList

class ReadRelease(IntEnum):
    PRIVATE = 0  # accessible only to users with an authorised affiliation to the controller
    REGISTERED = 1 # accessible to any registered user
    PUBLIC = 2  # accessible to non-registered users # todo

class Control(BaseModel):
    release: ReadRelease
    time: datetime = Field(frozen=True, default=datetime.utcnow())

    @field_validator('time', mode='before')
    def validate_time(cls, v: datetime | Neo4jDateTime):
        if isinstance(v, Neo4jDateTime):
            return v.to_native()
        elif isinstance(v, datetime):
            return v
        else:
            raise ValidationError("time must be datetime.datetime or neo4j.time.DateTime")


class WriteStamp(BaseModel):
    user: int  # user id
    time: datetime

    @field_validator('time', mode='before')
    def validate_time(cls, v: datetime | Neo4jDateTime):
        if isinstance(v, Neo4jDateTime):
            return v.to_native()
        elif isinstance(v, datetime):
            return v
        else:
            raise ValidationError("time must be datetime.datetime or neo4j.time.DateTime")

class Controller(BaseModel):
    controls: Dict[int, Control]  # key should be team_id
    writes: List[WriteStamp]|None = Field(frozen=True, default=None) # for auditing

    @property
    def controllers(self) -> set[int]:
        return set(self.controls.keys())

    @property
    def release(self) -> ReadRelease:
        if not self.controls:
            return ReadRelease.PUBLIC
        return min([c.release for c in self.controls.values()])

    @property
    def created(self) -> datetime:
        return min([w.time for w in self.writes])

    @property
    def updated(self) -> datetime:
        return max([w.time for w in self.writes])

    def set_release(self, release: ReadRelease, team_id: int):
        self.controls[team_id].release = release

    def has_access(self, access: Access, access_teams: Set[int] = None) -> bool:
        if access is Access.READ:
            if self.release == ReadRelease.PUBLIC:
                return True
            elif access_teams:
                if self.release == ReadRelease.REGISTERED:
                    return True
                elif self.release == ReadRelease.PRIVATE:
                    if set(self.controls.keys()).intersection(access_teams):
                        return True
        else:
            if set(self.controls.keys()).intersection(access_teams):
                return True

        return False


class ControlledModel(BaseModel):
    controller: Controller

    def set_release(self, release: ReadRelease, team_id: int):
        self.controller.set_release(release, team_id)

class ControlledAggregate(Aggregate):
    _redacted_str: ClassVar = 'REDACTED'

    @abstractmethod
    def redacted(self, read_teams: List[int]) -> 'ControlledAggregate':
        """
            Provide a list of teams and return a version of the aggregate
                where data visible only to those with authorised read affiliation to those teams is visible.
        """
        raise NotImplementedError
