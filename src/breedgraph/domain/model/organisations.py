import logging

from pydantic import BaseModel, field_validator, ValidationError, Field
from typing import List, Optional

logger = logging.getLogger(__name__)

class TeamBase(BaseModel):
    name: str
    fullname: str
    parent_id: None|int = None

class  TeamInput(TeamBase):
    pass

class TeamOutput(TeamBase):
    id: int = Field(frozen=True)
    child_ids: None|List[int] = Field(frozen=True)

class TeamStored(TeamBase):
    id: int = Field(frozen=True)
    admin_ids: List[int] = Field(frozen=True)
    child_ids: None|List[int] = Field(frozen=True)

class OrganisationBase(BaseModel):
    teams: List[TeamBase]

    def __hash__(self):
        return hash(self.root.name)
    @property
    def root(self) -> TeamBase:
        for team in self.teams:  # should always be the first, this just ensures we can only return a root.
            if team.parent_id is None:
                return team

    def get_team(self, team_id: int):  # todo probably should be using a map here
        for team in self.teams:
            if isinstance(team, TeamStored) and team.id == team_id:
                return team

    def get_team_by_name_and_parent(self, name: str, parent_id: None|int):
        if parent_id is None:
            logger.warning("Looking for a team without a parent, this is always the root")
            if name.casefold == self.root.name.casefold():
                return self.root
        else:
            parent = self.get_team(parent_id)
            for team_id in parent.child_ids:
                team = self.get_team(team_id)
                if team.name.casefold() == name.casefold():
                    return team

class OrganisationInput(OrganisationBase):
    teams: List[TeamInput]

    @field_validator('teams')
    def teams(cls, l: List[TeamInput]) -> List[TeamInput]:
        if not len(l) == 1:
            raise ValidationError('Input organisation can only have one team')
        if l[0].parent_id:
            raise ValidationError('Input organisation root team must not have a parent')
        return l


class OrganisationStored(OrganisationBase):
    teams: List[TeamStored|TeamInput]

    @property   # re-declaring here to reflect modified type of root
    def root(self) -> TeamStored:
        for team in self.teams:
            if team.parent_id is None:
                return team
