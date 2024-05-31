import logging

from pydantic import BaseModel, field_validator, ValidationError, Field, computed_field


from typing import List, Dict

from .base import Entity, Aggregate

logger = logging.getLogger(__name__)

class TeamBase(BaseModel):
    name: str
    fullname: str
    parent: None | int = Field(frozen=True, default=None)

class  TeamInput(TeamBase):
    pass

class TeamStored(TeamBase, Entity):
    children: List[int] = Field(frozen=True, default=list())

    admins: List[int] = Field(frozen=True, default=list())
    readers: List[int] = Field(frozen=True, default=list())
    writers: List[int] = Field(frozen=True, default=list())
    curators: List[int] = Field(frozen=True, default=list())

    read_requests: List[int] = Field(frozen=True, default=list())
    write_requests: List[int] = Field(frozen=True, default=list())
    curate_requests: List[int] = Field(frozen=True, default=list())
    admin_requests: List[int] = Field(frozen=True, default=list())

class TeamOutput(TeamStored):
    pass

class Organisation(Aggregate):
    root_id: int
    teams: Dict[int, TeamInput|TeamStored] = dict()

    @classmethod
    def from_list(cls, teams_list: List[TeamStored]):
        root_id = None
        teams_map = dict()
        for team in teams_list:
            teams_map[team.id] = team
            if team.parent is None:
                root_id = team.id
        return cls(root_id=root_id, teams=teams_map)

    @property
    def root(self) -> TeamStored:
        return self.teams[self.root_id]

    @property
    def protected(self) -> str|None:
        if self.root.children:
            return "Cannot delete an organisation while its root has children"

    def add_team(self, team: TeamInput) -> int:  # returns temporary ID in case it is needed
        if not team.parent in self.teams:
            raise ValueError("Parent team is not in this organisation")
        for tid in self.teams[team.parent].children:
            if self.teams[tid].name.casefold() == team.name.casefold():
                raise ValueError("The parent team already has a child with this name")
        temp_id = -len(self.teams) - 1
        self.teams[temp_id] = team
        return temp_id

    def remove_team(self, team_id):
        team = self.teams[team_id]
        if team.children:
            raise ValueError("Cannot remove a team with children")
        self.teams.pop(team_id)

    def get_team(self, team_id: int=None, name: str=None, parent_id: None|int = None):
        if team_id is not None:
            return self.teams[team_id]
        elif parent_id is None:
            if name.casefold == self.root.name.casefold():
                return self.root
            else:
                teams = [t for t in self.teams.values() if t.name.casefold() == name.casefold()]
                if len(teams) == 1:
                    return teams[0]
                else:
                    raise ValueError("More than one team with a matching name, try specifying the parent")
        else:
            parent = self.teams[parent_id]
            for t in parent.children:
                team = self.teams[t]
                if team.name.casefold() == name.casefold():
                    return team