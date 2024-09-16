import logging

from enum import Enum
from pydantic import BaseModel, Field

from .base import StoredModel, Aggregate

from src.breedgraph.domain.events.accounts import EmailAdded, EmailVerified

from typing import List, Dict, Generator, ClassVar

logger = logging.getLogger(__name__)

class UserBase(BaseModel):
    label: ClassVar[str] = 'User'
    plural: ClassVar[str] = 'Users'

    name: str
    fullname: str
    email: str

class UserInput(UserBase):
    password_hash: str
    email_verified: bool = False

class UserStored(UserBase, StoredModel):
    password_hash: str
    email_verified: bool = False
    person: None|int = None  #ID for the corresponding Person

class UserOutput(UserBase, StoredModel):
    pass

class AccountBase(BaseModel):
    user: UserBase

class AccountInput(AccountBase):
    user: UserInput

class AccountStored(AccountBase, Aggregate):
    user: UserStored
    allowed_emails: List[str] = list() # tracked sets are not suited to strings due to collisions of hashes used to record changed elements
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

    def allow_email(self, email: str):
        self.allowed_emails.append(email)
        self.events.append(EmailAdded(email=email))

    def verify_email(self):
        self.user.email_verified = True
        self.events.append(EmailVerified(user=self.user.id))

class  AccountOutput(AccountBase):
    user: UserOutput
