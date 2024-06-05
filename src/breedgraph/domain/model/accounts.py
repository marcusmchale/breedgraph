import logging

from enum import Enum
from pydantic import BaseModel, Field

from .base import Entity, Aggregate

from src.breedgraph.domain.events import Event
from src.breedgraph.domain.events.accounts import EmailAdded, EmailVerified, AffiliationRequested, AffiliationApproved

from typing import List, Dict, Generator

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
    CURATE = "CURATE"
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
    heritable: bool  # if heritable equivalent access is provided to all children, recursively

class AffiliationStored(Affiliation):
    inherits_to: List[int] = Field(frozen=True)  # list of teams (ids only) that contribute to the team attribute
    admins: List[int] = Field(frozen=True)  # user ids that have admin privilege for the associated "team"

    @property
    def teams(self):
        return [self.team] + self.inherits_to

class AccountBase(BaseModel):
    user: UserBase

class AccountInput(AccountBase):
    user: UserInput

class AccountStored(AccountBase, Aggregate):
    user: UserStored
    affiliations: List[Affiliation|AffiliationStored] = list()
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

    @property
    def writes(self) -> List[int]:
        return [
            a.team for a in self.affiliations if
            a.access == Access.WRITE and a.authorisation== Authorisation.AUTHORISED
        ]

    @property
    def reads(self) -> List[int]:
        return [
            a.team for a in self.affiliations if
            a.access == Access.READ and a.authorisation == Authorisation.AUTHORISED
        ]

    @property
    def curates(self) -> List[int]:
        return [
            a.team for a in self.affiliations if
            a.access == Access.CURATE and a.authorisation == Authorisation.AUTHORISED
        ]

    @property
    def admins(self) -> List[int]:
        return [
            a.team for a in self.affiliations if
            a.access == Access.ADMIN and a.authorisation == Authorisation.AUTHORISED
        ]

    def allow_email(self, email:str):
        self.allowed_emails.append(email)
        self.events.append(EmailAdded(email=email))

    def verify_email(self):
        self.user.email_verified = True
        self.events.append(EmailVerified(user=self.user.id))

    def get_affiliation(self, team: int = None, access: Access = None) -> Affiliation|None:
        for a in self.affiliations:
            if all([
                team is None or team == a.team,
                access is None or access == a.access
            ]):
                return a

    def get_affiliations(self, team: int = None, access: Access = None, authorisation:Authorisation = None) -> Generator[Affiliation, None, None]:
        for a in self.affiliations:
            if all([
                any([
                    team is None,
                    team == a.team,
                    a.heritable and isinstance(a, AffiliationStored) and  team in a.teams
                ]),
                access is None or access == a.access,
                authorisation is None or authorisation == a.authorisation
            ]):
                yield a

    def request_affiliation(self, team: int, access: Access):
        # first check if already have this of affiliation
        affiliation = self.get_affiliation(team, access)
        if affiliation is not None:
            if isinstance(affiliation, AffiliationStored):
                if affiliation.authorisation in [Authorisation.RETIRED, Authorisation.DENIED]:
                    if self.user.id in affiliation.admins:
                        logger.debug("Resurrecting affiliation")
                        affiliation.authorisation = Authorisation.AUTHORISED
                    else:
                        logger.debug("Resurrecting affiliation request")
                        affiliation.authorisation = Authorisation.REQUESTED
                        self.events.append(AffiliationRequested(user=self.user.id, team=team, access=access))
                    return
            else:
                return

        affiliation = Affiliation(
            team=team,
            authorisation= Authorisation.REQUESTED,
            access=access,
            heritable=True  # requests should always be heritable to allow admins to approve for e.g. a lower level team
        )
        self.affiliations.append(affiliation)
        self.events.append(AffiliationRequested(user=self.user.id, team=team, access=access))

    def approve_affiliation(self, team:int, access: Access, heritable: bool):
        affiliation = self.get_affiliation(team=team, access=access)
        if affiliation is not None:
            affiliation.authorisation = Authorisation.AUTHORISED
            affiliation.heritable = heritable
        else:
            # The user may have requested affiliation to a parent team
            # in this case we create a new affiliation
            # leave the request affiliations in place, in case further approvals are desired
            affiliations = list(self.get_affiliations(team=team, access=access, authorisation=Authorisation.REQUESTED))
            if affiliations:
                affiliation = Affiliation(
                    team=team,
                    access=access,
                    heritable=heritable,
                    authorisation=Authorisation.AUTHORISED
                )
                self.affiliations.append(affiliation)
            else:
                raise ValueError("Only requested affiliations can be provided")

        self.events.append(AffiliationApproved(
            user=self.user.id,
            team=team,
            access=access
        ))


class  AccountOutput(AccountBase):
    user: UserOutput
    reads: List[int]
    writes: List[int]
    admins: List[int]
    curates: List[int]
