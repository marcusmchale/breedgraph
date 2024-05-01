import logging

from enum import Enum, IntEnum
from abc import abstractmethod
from src.breedgraph.domain.events.accounts import Event
from src.breedgraph.domain.model.organisations import TeamOutput
from pydantic import BaseModel, model_validator, field_validator, computed_field, model_validator, ValidationError, Field

from typing import Union, Optional, Dict, DefaultDict, Set, Tuple, TypedDict, List

logger = logging.getLogger(__name__)

class UserBase(BaseModel):
    name: str
    fullname: str
    email: str

class UserInput(UserBase):
    password_hash: str
    email_verified: bool = False

class UserOutput(UserBase):
    id: int = Field(frozen=True)

class UserStored(UserInput):
    id: int = Field(frozen=True)

    def to_output(self):
        return UserOutput(
            id=self.id,
            name=self.name,
            fullname=self.fullname,
            email=self.email
        )

class Access(str, Enum):
    READ = "READ"
    WRITE = "WRITE"
    ADMIN = "ADMIN"

class Authorisation(str, Enum):
    REQUESTED = 'REQUESTED'  # the user has requested an affiliation, can be removed by user or admin, authorised or denied by admin.
    AUTHORISED = 'AUTHORISED'  # user has requested then been authorised by an admin or IS and admin of this team or its parent, may not be removed, only retired.
    RETIRED = 'RETIRED'  # requested, authorised then later retired, can re-authorise, may not be removed, only denied
    DENIED = 'DENIED'  # requested then denied/revoked without authorisation, currently handled the same as retired but may be useful as a record of the request

class Affiliation(BaseModel):
    team: int
    access: Access
    authorisation: Authorisation
    heritable: bool = True  # if heritable equivalent access is provided to all children, recursively

class AccountBase(BaseModel):
    user: UserBase

class AccountInput(AccountBase):
    user: UserInput

class  AccountOutput(AccountBase):
    user: UserOutput
    reads: List[int]
    writes: List[int]
    admins: List[int]

class AccountStored(AccountBase):
    user: UserStored
    affiliations: List[Affiliation] = list()
    allowed_emails: List[str] = list()
    allowed_users: List[int] = Field(default=list(), frozen=True)
    events: List[Event] = list()

    def __hash__(self):
        return hash(self.user.id)
