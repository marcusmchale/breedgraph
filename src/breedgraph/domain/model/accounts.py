import logging

from abc import ABC
from dataclasses import dataclass, field
from enum import Enum

from src.breedgraph.service_layer.tracking.wrappers import asdict
from src.breedgraph.domain.events.accounts import EmailAdded, EmailVerified

from .base import LabeledModel, StoredModel, Aggregate, SerializableMixin

from typing import List, ClassVar, Dict, Any, Self

logger = logging.getLogger(__name__)

class OntologyRole(Enum):
    VIEWER = "viewer"  # read only
    CONTRIBUTOR = "contributor"  # Can propose changes
    EDITOR = "editor"           # Can commit versions
    ADMIN = "admin"             # Can manage roles

@dataclass
class UserBase(ABC):
    label: ClassVar[str] = 'User'
    plural: ClassVar[str] = 'Users'

    name: str = ''
    fullname: str = ''
    email: str = ''
    ontology_role: OntologyRole = OntologyRole.CONTRIBUTOR
    ontology_role_requested: OntologyRole|None = None

    def model_dump(self):
        dump = asdict(self)
        dump['ontology_role'] = dump['ontology_role'].value
        dump['ontology_role_requested'] = dump['ontology_role_requested'].value if 'ontology_role_requested' in dump else None
        return dump

    def __post_init__(self):
        if isinstance(self.ontology_role, str):
            self.ontology_role = OntologyRole(self.ontology_role)
        if isinstance(self.ontology_role_requested, str):
            self.ontology_role_requested = OntologyRole(self.ontology_role_requested)

@dataclass
class UserInput(UserBase, LabeledModel):
    password_hash: str = ''
    email_verified: bool = False

@dataclass(unsafe_hash=True)
class UserStored(UserBase, StoredModel):
    password_hash: str = ''
    email_verified: bool = False
    person: None|int = None  #ID for the corresponding Person

@dataclass
class UserOutput(UserBase, LabeledModel):
    id : int|None = None
    email_verified: bool = False

    @classmethod
    def from_stored(cls, stored: UserStored) -> Self:
        return cls(
            id = stored.id,
            name = stored.name,
            fullname = stored.fullname,
            email = stored.email,
            ontology_role = stored.ontology_role,
            email_verified = stored.email_verified
        )

@dataclass
class AccountBase(SerializableMixin, ABC):
    user: UserBase

@dataclass
class AccountInput(AccountBase):
    user: UserInput

    def model_dump(self):
        return {
            'user': self.user.model_dump()
        }

@dataclass(eq=False)
class AccountStored(Aggregate, AccountBase):
    user: UserStored
    allowed_emails: List[str] = field(default_factory=list)
    # tracked sets are not suited to strings due to collisions of hashes used to record changed elements
    allowed_users: List[int] = field(default_factory=list)

    @property
    def root(self):
        return self.user

    @property
    def protected(self):
        if self.user.email_verified:
            return "Accounts with a verified email cannot be removed"
        else:
            return False

    def model_dump(self):
        return {
            'user': self.user.model_dump(),
            'allowed_emails': self.allowed_emails,
            'allowed_users': self.allowed_users,
        }

    def allow_email(self, email: str):
        self.allowed_emails.append(email)
        self.events.append(EmailAdded(email=email))

    def verify_email(self):
        self.user.email_verified = True
        self.events.append(EmailVerified(user=self.user.id))

    def remove_email(self, email: str):
        email_to_remove = None # need case insensitive remove
        for allowed_email in self.allowed_emails:
            if allowed_email.casefold() == email.casefold():
                email_to_remove = allowed_email
                break

        if email_to_remove:
            self.allowed_emails.remove(email)
        else:
            raise ValueError(f"Email {email} not found in allowed emails")

    def can_contribute_ontology(self) -> bool:
        """Only these roles can contribute to ontology"""
        return self.user.ontology_role in [OntologyRole.CONTRIBUTOR, OntologyRole.EDITOR, OntologyRole.ADMIN]

    def can_commit_ontology_version(self) -> bool:
        """Only editors and admins can commit new versions"""
        return self.user.ontology_role in [OntologyRole.EDITOR, OntologyRole.ADMIN]

    def can_manage_ontology_roles(self) -> bool:
        """Only admins can manage ontology roles"""
        return self.user.ontology_role == OntologyRole.ADMIN

@dataclass
class  AccountOutput(AccountBase):
    user: UserOutput
    allowed_emails: List[str] = field(default_factory=list)

    def model_dump(self):
        return {
            'user': self.user.model_dump(),
            'allowed_emails': self.allowed_emails
        }
