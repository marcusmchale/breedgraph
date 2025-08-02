import networkx as nx
import copy

from abc import abstractmethod
from pydantic import BaseModel, Field, ValidationError, field_validator
from enum import Enum
from datetime import datetime
from neo4j.time import DateTime as Neo4jDateTime

from typing import Dict, List, ClassVar, Set, Type

from src.breedgraph.domain.model.organisations import Access
from src.breedgraph.domain.model.base import Aggregate, StoredModel, RootedAggregate, TreeAggregate
from src.breedgraph.custom_exceptions import IllegalOperationError

class ReadRelease(Enum):
    PRIVATE = 'PRIVATE'  # accessible only to users with an authorised affiliation to the controller
    REGISTERED = 'REGISTERED' # accessible to any registered user
    PUBLIC = 'PUBLIC'  # accessible to non-registered users  #  todo, currently this is not fully implemented

class Control(BaseModel):
    release: ReadRelease
    # we are not using the time now, but keep the control object and time in case of future behaviour requirements
    # For example,
    # currently the release is just set by the "minimum" current release level,
    # but we could alternatively set the release behaviour according to the most recent release set
    #
    time: datetime = Field(default=datetime.now())

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
    def teams(self) -> set[int]:
        return set(self.controls.keys())

    @property
    def release(self) -> ReadRelease:
        if not self.controls:
            return ReadRelease.PUBLIC
        releases = set([c.release for c in self.controls.values()])
        if ReadRelease.PRIVATE in releases:
            return ReadRelease.PRIVATE
        elif ReadRelease.REGISTERED in releases:
            return ReadRelease.REGISTERED
        else:
            return ReadRelease.PUBLIC

    @property
    def created(self) -> datetime:
        return min([w.time for w in self.writes])

    @property
    def updated(self) -> datetime:
        return max([w.time for w in self.writes])

    def set_release(self, team_id: int, release: ReadRelease):
        self.controls[team_id].release = release

    def has_access(self, access: Access, user_id: int = None, access_teams: Set[int] = None) -> bool:
        if access_teams is None:
            access_teams = set()

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

    @abstractmethod
    def redacted(
            self,
            controller: Controller,
            user_id = None,
            read_teams = None
    ) -> 'ControlledModel':
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
            Be sure to include any removed models in the report, to support control over removal
        """
        raise NotImplementedError

    @abstractmethod
    def redacted(
            self,
            controllers: Dict[str, Dict[int, Controller]], # keyed as {label: {model_id : controller}}
            user_id = None,
            read_teams = None
    ) -> 'ControlledAggregate':
        """
            Return a version of the aggregate where data is redacted and/or filtered
            to suit registered users (i.e. has user_id)
            or private access (read teams).
        """
        raise NotImplementedError

    def can_remove(
            self,
            controllers: Dict[str, Dict[int, Controller]],
            user_id = None,
            curate_teams = None
    ) -> bool:
        """
        Return a boolean indicating whether the aggregate can be removed by the given user and curate teams.
        """
        for model in self.controlled_models:
            controller = controllers[model.label][model.id]
            if not controller.has_access(Access.CURATE, user_id, curate_teams):
                return False
        else:
            return True

class ControlledRootedAggregate(RootedAggregate, ControlledAggregate):
    default_model_class: ClassVar[Type[ControlledModel]]

    @property
    def controlled_models(self) -> List[ControlledModel]:
        return [
            model for model in nx.get_node_attributes(self._graph, "model").values()
            if isinstance(model, ControlledModel)
        ]

    def redacted(
            self,
            controllers: Dict[str, Dict[int, Controller]],
            user_id = None,
            read_teams = None
    ) -> 'ControlledRootedAggregate|None':

        if read_teams is None:
            read_teams = set()

        g = copy.deepcopy(self._graph)
        for node_id in list(g.nodes):
            entry = g.nodes[node_id]['model']
            label = entry.label
            if not node_id in controllers[label]:
                # controller not found for this node, may be input
                raise IllegalOperationError(f"Controller not found for node {node_id}")
            controller = controllers[label][node_id]
            if not controller.has_access(Access.READ, user_id, read_teams):
                if node_id == self.get_root_id():
                    redacted_root = entry.redacted(
                        controller = controller,
                        user_id = user_id,
                        read_teams = read_teams
                    )
                    g.nodes[node_id]['model'] = redacted_root
                else:
                    self.remove_node_and_reconnect(g, node_id, label=self.default_edge_label)

        aggregate = self.__class__()
        aggregate._graph = g
        return aggregate


class ControlledTreeAggregate(ControlledRootedAggregate, TreeAggregate):
    pass
