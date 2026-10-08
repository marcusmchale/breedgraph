"""
People who took part in research, for attribution. See docs/person.md.

A Person stores only what attribution needs. Erasing a Person removes identifying data,
leaving a record with its ID so contributions remain attributed to an anonymous person.
"""
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from abc import ABC

from breedgraph.custom_exceptions import IllegalOperationError, UnauthorisedOperationError

from .base import EnumLabeledModel
from .controls import ControlledModel, ControlledAggregate, Controller, ControlledModelLabel, Access

from typing import List, Set, ClassVar, Dict

import logging
import re
logger = logging.getLogger(__name__)


ORCID_PATTERN = re.compile(r'^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$')


def normalise_orcid(orcid: str) -> str:
    """An ORCID iD in its 16-character form, accepting the https://orcid.org/ URI form. Raises if not valid."""
    orcid = (orcid or '').strip().removeprefix('https://orcid.org/').removeprefix('http://orcid.org/').upper()
    if not ORCID_PATTERN.match(orcid):
        raise IllegalOperationError("Not a valid ORCID iD")
    # Check digit, ISO 7064 11,2
    total = 0
    for digit in orcid.replace('-', '')[:-1]:
        total = (total + int(digit)) * 2
    check = (12 - total % 11) % 11
    if orcid[-1] != ('X' if check == 10 else str(check)):
        raise IllegalOperationError("Not a valid ORCID iD")
    return orcid


class LawfulBasis(str, Enum):
    """The GDPR basis for holding a Person record, Art. 6(1)"""
    PUBLIC_TASK = "PUBLIC_TASK"  # e)
    LEGITIMATE_INTEREST = "LEGITIMATE_INTEREST"  # f)


@dataclass(eq=False)
class PersonBase(ABC):
    label: ClassVar[ControlledModelLabel] = ControlledModelLabel.PERSON

    name: str | None = None  # display name used for attribution
    teams: List[int] = field(default_factory=list)  # affiliation, references to stored Team IDs

    basis: LawfulBasis = LawfulBasis.PUBLIC_TASK
    informed_attestation: bool = False  # the creator confirmed the person was informed that the record is held


@dataclass(eq=False)
class PersonInput(PersonBase, EnumLabeledModel):

    def __post_init__(self):
        self.name = (self.name or '').strip()
        if not self.name:
            raise IllegalOperationError("A Person requires a name")
        if not self.informed_attestation:
            raise IllegalOperationError("The person must have been informed that this record is held")
        if not isinstance(self.basis, LawfulBasis):
            self.basis = LawfulBasis(self.basis)


@dataclass(eq=False)
class PersonStored(PersonBase, ControlledModel, ControlledAggregate):
    orcid: str | None = None  # set only by the linked user, verified through ORCID sign-in
    user: int | None = None  # the linked user, who has subject rights over this record
    claims: List[int] = field(default_factory=list)  # users requesting to be linked, pending approval

    recorded_by: int | None = None
    recorded_at: datetime | None = None
    erased_at: datetime | None = None

    @property
    def controlled_models(self) -> List[ControlledModel]:
        return [self]

    @property
    def root(self) -> ControlledModel:
        return self

    @property
    def protected(self) -> str | None:
        return "Persons are erased rather than removed, so attribution to them is kept"

    @property
    def erased(self) -> bool:
        return self.erased_at is not None

    def is_subject(self, user_id: int | None) -> bool:
        return user_id is not None and user_id == self.user

    def _id_only(self, user_id: int | None = None) -> 'PersonStored':
        return replace(
            self,
            name=None,
            teams=list(),
            orcid=None,
            user=None,
            # users see their own request to be linked, so they can withdraw it, but not others'
            claims=[user_id] if user_id is not None and user_id in self.claims else list(),
            recorded_by=None,
            recorded_at=None
        )

    def redacted(
            self,
            controllers: Dict[str, Dict[int, Controller]],
            user_id=None,
            read_teams=None
    ) -> 'PersonStored|None':
        """
        Readers of the record, and the linked user, see the full record.
        Other registered users see only the ID, which they can use to find who controls the record.
        Anonymous users see nothing.
        """
        controller = controllers[self.label][self.id]
        if read_teams is None:
            read_teams = set()

        if self.is_subject(user_id) or controller.has_access(Access.READ, user_id, read_teams):
            return self
        if user_id is None:
            return None
        return self._id_only(user_id)

    def erase(self, agent_id: int, controller: Controller, admin_teams: Set[int]) -> None:
        """
        Remove identifying data, keeping the ID, controls, basis and record of who recorded it.
        Admins of the controlling teams and the linked user can erase.
        """
        if self.erased:
            raise IllegalOperationError("This Person is already erased")
        if not (self.is_subject(agent_id) or controller.has_access(Access.ADMIN, agent_id, admin_teams)):
            raise UnauthorisedOperationError("Only admins of the controlling teams or the linked user can erase a Person")

        self.name = None
        self.teams = list()
        self.orcid = None
        self.user = None
        self.claims = list()
        self.erased_at = datetime.now(timezone.utc)

    def set_orcid(self, agent_id: int, orcid: str) -> None:
        """Only the linked user sets the ORCID iD, verified through ORCID sign-in"""
        if not self.is_subject(agent_id):
            raise UnauthorisedOperationError("Only the linked user can set the ORCID iD of a Person")
        self.orcid = normalise_orcid(orcid)

    def remove_orcid(self, agent_id: int) -> None:
        if not self.is_subject(agent_id):
            raise UnauthorisedOperationError("Only the linked user can remove the ORCID iD of a Person")
        self.orcid = None

    def _require_linkable(self) -> None:
        if self.erased:
            raise IllegalOperationError("An erased Person cannot be linked to an account")
        if self.user is not None:
            raise IllegalOperationError("This Person is already linked to an account")

    def request_claim(self, user_id: int) -> None:
        """A registered user asks to be linked to this Person, for admins of the controlling teams to decide"""
        self._require_linkable()
        if user_id in self.claims:
            raise IllegalOperationError("You have already asked to be linked to this Person")
        self.claims.append(user_id)

    def withdraw_claim(self, user_id: int) -> None:
        if user_id not in self.claims:
            raise IllegalOperationError("No request to link this Person was found")
        self.claims.remove(user_id)

    def _require_admin(self, agent_id: int, controller: Controller, admin_teams: Set[int]) -> None:
        if not controller.has_access(Access.ADMIN, agent_id, admin_teams):
            raise UnauthorisedOperationError("Only admins of the controlling teams can decide requests to link a Person")

    def approve_claim(self, agent_id: int, user_id: int, controller: Controller, admin_teams: Set[int]) -> None:
        """Link the requesting user. Other pending requests are dropped."""
        self._require_admin(agent_id, controller, admin_teams)
        if user_id not in self.claims:
            raise IllegalOperationError("No request to link this Person was found for the user")
        self.link(user_id)

    def reject_claim(self, agent_id: int, user_id: int, controller: Controller, admin_teams: Set[int]) -> None:
        self._require_admin(agent_id, controller, admin_teams)
        self.withdraw_claim(user_id)

    def link(self, user_id: int) -> None:
        """Link a user, who gains subject rights over the record. The caller authorises the link."""
        self._require_linkable()
        self.user = user_id
        self.claims = list()

    def unlink(self, agent_id: int, controller: Controller, admin_teams: Set[int]) -> None:
        """The linked user or admins of the controlling teams can remove the link"""
        if self.user is None:
            raise IllegalOperationError("This Person is not linked to an account")
        if not (self.is_subject(agent_id) or controller.has_access(Access.ADMIN, agent_id, admin_teams)):
            raise UnauthorisedOperationError("Only the linked user or admins of the controlling teams can unlink a Person")
        self.user = None

    def to_output(self) -> 'PersonOutput':
        return PersonOutput(
            id=self.id,
            name=self.name,
            teams=list(self.teams),
            basis=self.basis,
            informed_attestation=self.informed_attestation,
            orcid=self.orcid,
            user=self.user,
            claims=list(self.claims),
            recorded_by=self.recorded_by,
            recorded_at=self.recorded_at,
            erased_at=self.erased_at
        )


@dataclass(eq=False)
class PersonOutput(PersonBase, EnumLabeledModel):
    id: int = None
    orcid: str | None = None
    user: int | None = None
    claims: List[int] = field(default_factory=list)
    recorded_by: int | None = None
    recorded_at: datetime | None = None
    erased_at: datetime | None = None
