"""
Transfer of control over controlled entities between teams.

An admin of the current control teams offers entities to a recipient team.
An admin of the recipient team accepts, choosing the new control teams from the recipient team
and the teams below it, and the release level for the new controls.
See docs/control-transfer.md.
"""
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC

from datetime import datetime

from breedgraph.custom_exceptions import IllegalOperationError, UnauthorisedOperationError

from .base import LabeledModel, StoredModel, Aggregate
from .controls import ControlledModelLabel, ReadRelease

from typing import ClassVar, List, Set


class ControlTransferStatus(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class ControlledEntity:
    """A controlled model. Transfers apply to the model itself, not to other models in its aggregate."""
    label: ControlledModelLabel
    id: int


@dataclass(eq=False)
class ControlTransferBase(ABC):
    label: ClassVar[str] = 'ControlTransfer'
    plural: ClassVar[str] = 'ControlTransfers'

    entities: List[ControlledEntity] = field(default_factory=list)
    from_teams: List[int] = field(default_factory=list)  # current control teams giving up control
    recipient_team: int = None  # chosen by the offering side, often an organisation root
    keep_from_teams: bool = False  # shared control: from_teams keep control as well
    offered_by: int = None


@dataclass(eq=False)
class ControlTransferInput(ControlTransferBase, LabeledModel):

    def __post_init__(self):
        self.from_teams = sorted(set(self.from_teams or []))
        if not self.entities:
            raise IllegalOperationError("A control transfer requires entities")
        if not self.from_teams:
            raise IllegalOperationError("A control transfer requires teams to transfer from")
        if self.recipient_team is None:
            raise IllegalOperationError("A control transfer requires a recipient team")
        if self.offered_by is None:
            raise IllegalOperationError("A control transfer requires the offering user")

    def check_offer(self, admin_teams: Set[int]) -> None:
        """The offering user must be an admin of every team giving up control."""
        if not set(self.from_teams).issubset(admin_teams):
            raise UnauthorisedOperationError("Admin access to every team giving up control is required to offer a transfer")


@dataclass(eq=False)
class ControlTransferStored(ControlTransferBase, StoredModel, Aggregate):
    status: ControlTransferStatus = ControlTransferStatus.PENDING

    to_teams: List[int] = field(default_factory=list)  # chosen by the receiving side on acceptance
    release: ReadRelease | None = None  # chosen by the receiving side on acceptance

    offered_at: datetime | None = None
    accepted_by: int | None = None
    accepted_at: datetime | None = None
    rejected_by: int | None = None
    rejected_at: datetime | None = None
    cancelled_by: int | None = None
    cancelled_at: datetime | None = None

    @property
    def root(self) -> 'ControlTransferStored':
        return self

    @property
    def protected(self) -> str | None:
        return "Control transfers are kept as a record"

    @property
    def teams_to_end(self) -> Set[int]:
        return set() if self.keep_from_teams else set(self.from_teams)

    def _require_pending(self) -> None:
        if self.status is not ControlTransferStatus.PENDING:
            raise IllegalOperationError(f"Control transfer is {self.status.value.lower()}, not pending")

    def accept(
            self,
            agent_id: int,
            admin_teams: Set[int],
            recipient_teams: Set[int],
            to_teams: Set[int],
            release: ReadRelease = ReadRelease.PRIVATE
    ) -> None:
        """
        :param agent_id: the accepting user
        :param admin_teams: teams the accepting user is an admin of, directly or through heritable affiliations
        :param recipient_teams: the recipient team and the teams below it
        :param to_teams: the new control teams
        :param release: the release level for the new controls
        """
        self._require_pending()
        if self.recipient_team not in admin_teams:
            raise UnauthorisedOperationError("Admin access to the recipient team is required to accept a transfer")
        if not to_teams:
            raise IllegalOperationError("Accepting a transfer requires teams to take control")
        if not to_teams.issubset(recipient_teams):
            raise IllegalOperationError("Teams taking control must be the recipient team or teams below it")
        if not to_teams.issubset(admin_teams):
            raise UnauthorisedOperationError("Admin access to every team taking control is required to accept a transfer")
        if to_teams.intersection(self.from_teams):
            raise IllegalOperationError("Teams taking control must not include teams giving up control")

        self.to_teams = sorted(to_teams)
        self.release = release
        self.accepted_by = agent_id
        self.status = ControlTransferStatus.ACCEPTED

    def reject(self, agent_id: int, admin_teams: Set[int]) -> None:
        self._require_pending()
        if self.recipient_team not in admin_teams:
            raise UnauthorisedOperationError("Admin access to the recipient team is required to reject a transfer")
        self.rejected_by = agent_id
        self.status = ControlTransferStatus.REJECTED

    def cancel(self, agent_id: int, admin_teams: Set[int]) -> None:
        self._require_pending()
        if not set(self.from_teams).issubset(admin_teams):
            raise UnauthorisedOperationError("Admin access to every team giving up control is required to cancel a transfer")
        self.cancelled_by = agent_id
        self.status = ControlTransferStatus.CANCELLED
