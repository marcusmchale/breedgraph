import logging

from enum import Enum
from abc import abstractmethod
from src.breedgraph.domain.events.accounts import Event
from pydantic import BaseModel, model_validator, field_validator, computed_field, model_validator
from collections import defaultdict, Mapping

# typing only
from typing import Union, Optional, List, Dict, DefaultDict, Set, Tuple

logger = logging.getLogger(__name__)

class Name(BaseModel):
    display: str
    full: Optional[str] = None
    @computed_field
    @property
    def lower(self) -> str:
        return self.display.casefold()

    @model_validator(mode='after')
    def autofill_full(self) -> 'Name':
        if self.full is None:
            self.full = self.display
        return self

    def __hash__(self) -> int:
        return hash(self.lower)

    def __eq__(self, other):
        if isinstance(other, type(self)):
            return self.lower == other.lower
        elif isinstance(other, str):
            return self.lower == other.casefold()
        raise ValueError("Name can only be tested for equivalence to Name or str")

class Email(BaseModel):
    address: str
    verified: bool

    @property
    def lower(self):
        return self.address.casefold()  # not a true guarantee but should catch some redundancy

    def __hash__(self):
        return hash(self.lower)

    def __eq__(self, other):
        if isinstance(other, type(self)):
            return self.lower == other.lower
        elif isinstance(other, str):
            return self.lower == other.casefold()
        raise ValueError("Email can only be tested for equivalence to Email or str")

class UserBase(BaseModel):
    name: Name
    email: Email

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other):
        if isinstance(other, type(self)):
            return self.name == other.name
        raise ValueError("Can't compare User to other types")

class UserInput(UserBase):
    password_hash: str


class UserOutput(UserBase):
    id: int

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other):
        if isinstance(other, type(self)):
            return self.id == other.id
        UserBase.__eq__(self, other)

class UserStored(UserOutput):
    password_hash: str

class TeamBase(BaseModel):
    name: Name
    parent_id: Optional[int] = None

    def __hash__(self) -> int:
        return hash((self.name, self.parent_id))

    def __eq__(self, other):
        if type(other) == type(self) and other.parent_id == self.parent_id:
            return self.name == other.name
        else:
            return False

class TeamInput(TeamBase):
    pass

class TeamOutput(TeamBase):
    id: int

    def __hash__(self) -> int:
        return hash((self.id, self.parent_id))

    def __eq__(self, other):
        if isinstance(other, type(self)) and other.parent_id == self.parent_id:
            return self.id == other.id
        elif isinstance(other, TeamBase):
            return TeamBase.__eq__(other, self)
        elif isinstance(other, int):
            return self.id == other
        else:
            return False

class TeamStored(TeamOutput):
    pass



#class TeamTree(TeamStored):
#    children: List['TeamTree']
#
#class Organisation(BaseModel):  # tree structure
#    tree: TeamTree
#
#    @property
#    def name(self) -> str:  #not sure if this will work with pydantic... maybe
#        return self.tree.name
#
#    @property
#    def fullname(self) -> str:
#        return self.tree.fullname
#
#    @property
#    def id(self) -> int:
#        return self.tree.id
#
#    @property
#    def teams(self):
#        return self.teams_dict
#
#    @property
#    def teams_list(self) -> List[TeamStored]:
#        teams = list()
#        def add_to_list(tree: TeamTree):
#            teams.append(TeamStored(**tree.dict()))
#            for child in tree.children:
#                add_to_list(child)
#
#        add_to_list(self.tree)
#        return teams
#
#    @property
#    def teams_dict(self) -> Dict[TeamStored, TeamStored]:
#        teams = dict()
#        def add_children(parent_dict: Dict, tree: TeamTree):
#            key = TeamStored(**tree.dict())
#            parent_dict[key] = dict()
#            for child in tree.children:
#                add_children(parent_dict[key], child)
#
#        add_children(teams, self.tree)
#        return teams
#

class AffiliationType(Enum):
    READ = 1
    WRITE = 2
    ADMIN = 3

class Authorisation(Enum):
    REQUESTED = 1
    AUTHORISED = 2
    RETIRED = 3
    DENIED = 4

class Affiliation(BaseModel):
    type: AffiliationType
    authorisation: Authorisation
    team: [int|TeamInput|TeamStored]

class AffiliationsHolder:
    def __init__(self, affiliations: Optional[List[Affiliation]] = None):
        if affiliations is None:
            affiliations = list()
        self.affiliations = affiliations

    def get(
            self,
            affiliation_types: Optional[List[AffiliationType]] = None,
            authorisations: Optional[List[Authorisation]] = None,
            teams: Optional[List[int|TeamInput|TeamStored]] = None
    ):
        return [a for a in self.affiliations if self.is_matched(a, affiliation_types, authorisations, teams)]

    @staticmethod
    def is_matched(
            affiliation: Affiliation,
            affiliation_types: Optional[List[AffiliationType]],
            authorisations: Optional[List[Authorisation]],
            teams: Optional[List[int|TeamInput|TeamStored]]
    ):
        return all([
            affiliation_types is None or affiliation.type in affiliation_types,
            authorisations is None or affiliation.authorisation in authorisations,
            teams is None or affiliation.team in teams
        ])

class AccountBase(BaseModel):
    user: UserBase

    def __eq__(self, other):
        if isinstance(other, AccountBase):
            return self.user == other.user
        return False

    def __hash__(self):
        return hash(self.user)

class AccountInput(AccountBase):
    user: UserInput

class AccountOutput(AccountBase):
    user: UserOutput
    affiliations: AffiliationsHolder = AffiliationsHolder()
    allowed_emails: List[Email] = list()

    @model_validator(mode='after')
    def allow_emails_for_admins_only(self) -> 'AccountOutput':
        if self.allowed_emails and not self.affiliations[AffiliationType.ADMIN]:
            raise ValueError('only admins can have allowed emails')
        return self

class AccountStored(AccountOutput):
    user: UserStored
    events: list[Event] = []

