import logging

from pydantic import BaseModel, field_validator, ValidationError, Field
from typing import List


logger = logging.getLogger(__name__)

class TeamBase(BaseModel):
    name: str
    fullname: str

class  TeamInput(TeamBase):
    parent: None | int = Field(frozen=True, default=None)

class TeamOutput(TeamInput):
    id: int = Field(frozen=True)
    children: None | List[int] = Field(frozen=True)
    # lists of users with affiliations (including inherited)
    admins: List[int] = Field(frozen=True)
    readers: List[int] = Field(frozen=True)
    writers: List[int] = Field(frozen=True)
    read_requests: List[int] = Field(frozen=True)
    write_requests: List[int] = Field(frozen=True)
    admin_requests: List[int] = Field(frozen=True)

class TeamStored(TeamOutput):
    pass

class OrganisationBase(BaseModel):
    teams: List[TeamInput]

    def __hash__(self):
        return hash(self.root.name)
    @property
    def root(self) -> TeamInput:
        for team in self.teams:  # should always be the first, this just ensures we can only return a root.
            if team.parent is None:
                return team

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

class OrganisationInput(OrganisationBase):
    teams: List[TeamInput]

    @field_validator('teams')
    def teams(cls, l: List[TeamInput]) -> List[TeamInput]:
        if not len(l) == 1:
            raise ValidationError('Input organisation can only have one team')
        if l[0].parent:
            raise ValidationError('Input organisation root team must not have a parent')
        return l

class OrganisationStored(OrganisationBase):
    teams: List[TeamStored|TeamInput]

    @property   # re-declaring here to reflect modified type
    def root(self) -> TeamStored:
        for team in self.teams:
            if team.parent is None:
                return team
