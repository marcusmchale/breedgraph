import logging

from enum import Enum, IntEnum
from abc import abstractmethod
from src.breedgraph.domain.events.accounts import Event
from src.breedgraph.domain.model.organisations import TeamOutput
from pydantic import BaseModel, model_validator, field_validator, computed_field, model_validator, ValidationError, Field

from typing import Union, Optional, Dict, DefaultDict, Set, Tuple, TypedDict, List

logger = logging.getLogger(__name__)

class UserBase(BaseModel):
    fullname: str
    email: str

class UserInput(UserBase):
    name: str
    password_hash: str
    email_verified: bool = False

class UserOutput(UserBase):
    id: int = Field(frozen=True)

class UserStored(UserInput):
    id: int = Field(frozen=True)

    def to_output(self):
        return UserOutput(
            id=self.id,
            fullname=self.fullname,
            email=self.email
        )

class Access(str, Enum):
    NONE = None
    READ = 'READ'
    WRITE = 'WRITE'
    ADMIN = 'ADMIN'

class Authorisation(str, Enum):
    NONE = None
    REQUESTED = 'REQUESTED'  # the user has requested an affiliation, can be removed by user or admin, authorised or denied by admin.
    AUTHORISED = 'AUTHORISED'  # user has requested then been authorised by an admin or IS and admin of this team or its parent, may not be removed, only retired.
    RETIRED = 'RETIRED'  # requested, authorised then later retired, can re-authorise, may not be removed, only denied
    DENIED = 'DENIED'  # future requests denied, can't authorise,
    # this is included to support request denial but may not be needed.
    # consider only applying denied in strong cases, otherwise just leave the request active.

class Affiliation(BaseModel):
    team: int = Field(frozen=True)
    access: Access = Field(frozen=True)
    authorisation: Authorisation
    heritable: bool = False  # if heritable provide the same read/admin to all children, recursively.

    def is_matched(
            self,
            teams: None | List[int] = None,
            access_types: None|List[Access] = None,
            authorisations: None|List[Authorisation] = None
    ):
        return all([
            teams is None or self.team in teams,
            access_types is None or self.access in access_types,
            authorisations is None or self.authorisation in authorisations,
        ])

class AccountBase(BaseModel):
    user: UserBase

class AccountInput(AccountBase):
    user: UserInput

class AccountOutput(AccountBase):
    user: UserOutput
    affiliations: List[Affiliation] = list()

class AccountStored(AccountBase):
    user: UserStored
    affiliations: List[Affiliation] = list()
    allowed_emails: List[str] = list()
    events: List[Event] = list()

    def __hash__(self):
        return hash(self.user.id)

    def get_affiliations(
            self,
            teams: None | List[int] = None,
            access_types: None|List[Access] = None,
            authorisations: None|List[Authorisation] = None
    ):
        for a in self.affiliations:
            if all(
                [
                    teams is None or a.team in teams,
                    access_types is None or a.access in access_types,
                    authorisations is None or a.authorisation in authorisations
                ]
            ):
                yield a
