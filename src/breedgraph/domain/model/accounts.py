import logging

from enum import Enum
from pydantic import BaseModel, Field

from .base import Entity, Aggregate

from typing import List

logger = logging.getLogger(__name__)

class UserBase(BaseModel):
    name: str
    fullname: str
    email: str

class UserInput(UserBase):
    password_hash: str
    email_verified: bool = False

class UserStored(UserBase, Entity):
    password_hash: str
    email_verified: bool = False
    person: None|int = None  #ID for the corresponding Person

class UserOutput(UserBase, Entity):
    pass

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

class AccountStored(AccountBase, Aggregate):
    user: UserStored
    affiliations: List[Affiliation] = list()
    allowed_emails: List[str] = list()  # tracked sets not suited to strings due to collisions of hashes
    allowed_users: List[int] = Field(frozen=True, default=list())

    @property
    def root(self):
        return self.user
    @property
    def protected(self):
        if self.user.email_verified:
            return "Accounts with a verified email cannot be removed"
        else:
            return False

class  AccountOutput(AccountBase):
    user: UserOutput
    reads: List[int]
    writes: List[int]
    admins: List[int]
