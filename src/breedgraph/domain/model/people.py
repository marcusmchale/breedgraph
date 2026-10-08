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
logger = logging.getLogger(__name__)


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

    def _id_only(self) -> 'PersonStored':
        return replace(
            self,
            name=None,
            teams=list(),
            orcid=None,
            user=None,
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
        return self._id_only()

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
        self.erased_at = datetime.now(timezone.utc)

    def to_output(self) -> 'PersonOutput':
        return PersonOutput(
            id=self.id,
            name=self.name,
            teams=list(self.teams),
            basis=self.basis,
            informed_attestation=self.informed_attestation,
            orcid=self.orcid,
            user=self.user,
            recorded_by=self.recorded_by,
            recorded_at=self.recorded_at,
            erased_at=self.erased_at
        )


@dataclass(eq=False)
class PersonOutput(PersonBase, EnumLabeledModel):
    id: int = None
    orcid: str | None = None
    user: int | None = None
    recorded_by: int | None = None
    recorded_at: datetime | None = None
    erased_at: datetime | None = None
