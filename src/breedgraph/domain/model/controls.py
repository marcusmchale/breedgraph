import networkx as nx
import copy

from abc import ABC, abstractmethod
from pydantic import BaseModel, RootModel, Field, ValidationError, ValidationInfo, field_validator, SerializeAsAny
from enum import IntEnum
from datetime import datetime
from neo4j.time import DateTime as Neo4jDateTime

from typing import Dict, List, Callable, Any, ClassVar, Set, Type


from src.breedgraph.domain.model.organisations import Access
from src.breedgraph.domain.model.base import Aggregate, StoredModel, RootedAggregate, TreeAggregate


class ReadRelease(IntEnum):
    PRIVATE = 0  # accessible only to users with an authorised affiliation to the controller
    REGISTERED = 1 # accessible to any registered user
    PUBLIC = 2  # accessible to non-registered users # todo

class Control(BaseModel):
    release: ReadRelease
    time: datetime = Field(default=datetime.utcnow())

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
    controls: Dict[int, Control] = dict() # key should be team_id
    writes: List[WriteStamp] = list()  # timestamps of writes to DB

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

    def set_release(self, team_id: int, release: ReadRelease):
        self.controls[team_id].release = release

    def has_access(self, access: Access, user_id: int = None, access_teams: Set[int] = None) -> bool:
        if access is Access.READ:
            if self.release == ReadRelease.PUBLIC:
                return True
            elif self.release == ReadRelease.REGISTERED and user_id is not None:
                return True
            elif self.release == ReadRelease.PRIVATE and set(self.controls.keys()).intersection(access_teams):
                return True
        else:
            if set(self.controls.keys()).intersection(access_teams):
                return True

        return False


class ControlledModel(StoredModel):
    redacted_str: ClassVar[str] = 'REDACTED'
    controller: Controller = Field(None, exclude=True)
    # todo reconsider better patterns.
    #  currently allowed to be None during init so controller can be inserted by controller layer in repository
    # could just wait to init in controller repository layer
    # but handier to reconstitute from db in nested repo layer responsible for retrieval of the core models

    def set_release(self, team_id: int, release: ReadRelease):
        self.controller.set_release(team_id, release)

    @abstractmethod
    def redacted(self) -> 'ControlledModel':
        """Do something like this to preserve data privacy when no read access is allowed"""
        return self.model_copy(deep=True, update={'name': self.redacted_str})


class ControlledAggregate(Aggregate):
    _redacted_str: ClassVar = 'REDACTED'

    @property
    @abstractmethod
    def controlled_models(self) -> List[ControlledModel]:
        """
            Should return a list of ControlledModels stored within the aggregate
            This is used by the controlled repository to create/update/delete controls.
        """
        raise NotImplementedError

    @abstractmethod
    def redacted(self, user_id: int = None, read_teams: Set[int] = None) -> 'ControlledAggregate':
        """
            Provide a list of teams and return a version of the aggregate
                where data visible only to those with authorised read affiliation to those teams is visible.
        """
        raise NotImplementedError


class ControlledRootedAggregate(RootedAggregate, ControlledAggregate):
    default_model_class: ClassVar[Type[ControlledModel]]

    @property
    def controlled_models(self) -> List[ControlledModel]:
        return list(nx.get_node_attributes(self._graph, "model").values())

    def redacted(self, user_id: int = None, read_teams: Set[int] = None) -> 'ControlledRootedAggregate|None':
        if read_teams is None:
            read_teams = set()

        g = copy.deepcopy(self._graph)

        root_id = self.get_root_id()
        for node_id in list(g.nodes):
            entry = g.nodes[node_id]['model']
            if not entry.controller.has_access(Access.READ, user_id, read_teams):
                if node_id == root_id:
                    redacted_root = entry.redacted()
                    g.nodes[node_id]['model'] = redacted_root
                else:
                    self.remove_node_and_reconnect(g, node_id, label=self.default_edge_label)

        aggregate = self.__class__()
        aggregate._graph = g
        return aggregate

class ControlledTreeAggregate(ControlledRootedAggregate, TreeAggregate):
    pass
