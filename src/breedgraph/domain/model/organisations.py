import logging

from pydantic import BaseModel, field_validator, ValidationError, Field
from typing import List

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
    read_requests: List[int] = Field(frozen=True, default=list())
    write_requests: List[int] = Field(frozen=True, default=list())
    admin_requests: List[int] = Field(frozen=True, default=list())

class TeamOutput(TeamStored):
    pass

class OrganisationBase(BaseModel):
    teams: List[TeamInput]

class OrganisationInput(OrganisationBase):
    teams: List[TeamInput]

    @field_validator('teams')
    def teams(cls, l: List[TeamInput]) -> List[TeamInput]:
        if not len(l) == 1:
            raise ValidationError('Input organisation can only have one team')
        if l[0].parent:
            raise ValidationError('Input organisation root team must not have a parent')
        return l

class OrganisationStored(OrganisationBase, Aggregate):
    teams: List[TeamStored|TeamInput]

    @property
    def root(self) -> TeamStored:
        for team in self.teams:
            if team.parent is None:
                return team
    @property
    def protected(self) -> str|None:
        if self.root.children:
            return "Cannot delete an organisation while its root has children"

    def get_team(self, team: int):  # todo probably should be using a map here
        for t in self.teams:
            if isinstance(t, TeamStored) and t.id == team:
                return t

    def get_team_by_name_and_parent(self, name: str, parent: None|int):
        if parent is None:
            logger.warning("Looking for a team without a parent, this is always the root")
            if name.casefold == self.root.name.casefold():
                return self.root
        else:
            parent = self.get_team(parent)
            for t in parent.children:
                team = self.get_team(t)
                if team.name.casefold() == name.casefold():
                    return team