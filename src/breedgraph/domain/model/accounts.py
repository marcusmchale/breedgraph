import logging

from enum import Enum, IntEnum
from abc import abstractmethod
from src.breedgraph.domain.events.accounts import Event
from pydantic import BaseModel, model_validator, field_validator, computed_field, model_validator, ValidationError, Field

from typing import Union, Optional, Dict, DefaultDict, Set, Tuple, TypedDict, List

logger = logging.getLogger(__name__)

class UserBase(BaseModel):
    name: str
    fullname: str
    email: str
    email_verified: bool = False

class UserInput(UserBase):
    password_hash: str

class UserOutput(UserBase):
    id: int = Field(frozen=True)

class UserStored(UserBase):
    id: int = Field(frozen=True)
    password_hash: str

class Access(Enum):
    NONE = 0
    READ = 1
    WRITE = 2
    ADMIN = 3

class Authorisation(Enum):
    NONE = 0
    REQUESTED = 1  # the user has requested an affiliation, can be removed by user or admin, authorised or denied by admin.
    AUTHORISED = 2  # user has requested then been authorised by an admin or IS and admin of this team or its parent, may not be removed, only retired.
    RETIRED = 3  # requested, authorised then later retired, can re-authorise, may not be removed, only denied
    DENIED = 4  # future requests denied, can't authorise,
    # this is included to support request denial but may not be needed.
    # consider only applying denied in strong cases, otherwise just leave the request active.

class Affiliation(BaseModel):
    # Affiliation rules:
    #  - Users request affiliation with a team
    #  - Admins can authorise that affiliation OR the same with one of its children.
    #  - Multiple relationships are allowed, including writing for multiple teams
    user_id: int = Field(frozen=True)
    team_id: int = Field(frozen=True)
    # that Team aggregate may include user references and other details, behaviours.
    access: Access = Field(frozen=True)
    authorisation: Authorisation
    heritable: bool = False  # if heritable provide the same read/admin to all children, recursively.

    def is_matched(
            self,
            user_ids: None|List[int] = None,
            team_ids: None | List[int] = None,
            access_types: None|List[Access] = None,
            authorisations: None|List[Authorisation] = None
    ):
        return all([
            user_ids is None or self.user_id in user_ids,
            team_ids is None or self.team_id in team_ids,
            access_types is None or self.access in access_types,
            authorisations is None or self.authorisation in authorisations,
        ])

class AccountBase(BaseModel):
    user: UserBase

class AccountInput(AccountBase):
    user: UserInput

#class AccountOutput(AccountBase):
#    user: UserOutput
#    affiliations: List[Affiliation] = list()
#    allowed_emails: List[str] = list()

class AccountStored(AccountBase):
    user: UserStored
    affiliations: List[Affiliation] = list()
    allowed_emails: List[str] = list()
    events: List[Event] = list()

    def __hash__(self):
        return hash(self.user.id)

    def get_affiliations(
            self,
            user_ids: None|List[int] = None,
            team_ids: None|List[int] = None,
            access_types: None|List[Access] = None,
            authorisations: None|List[Authorisation] = None
    ):
        for a in self.affiliations:
            if all(
                [
                    user_ids is None or a.user_id in user_ids,
                    team_ids is None or a.team_id in team_ids,
                    access_types is None or a.access in access_types,
                    authorisations is None or a.authorisation in authorisations
                ]
            ):
                yield a
