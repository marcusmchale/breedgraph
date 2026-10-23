"""
Invitations to register, replacing allowed emails. See docs/person.md §6.

An invitation holds the invited email address only until it is accepted, cancelled or expires,
when it is deleted. It may offer affiliations to teams the inviter administers, one or more accesses to each, and a Person
the inviter controls. The invited user accepts or declines each team, with every access offered to it, and the Person
when registering.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from abc import ABC

from breedgraph.custom_exceptions import IllegalOperationError, UnauthorisedOperationError

from .base import LabeledModel, StoredModel, Aggregate
from .controls import Access

from typing import ClassVar, List, Set


@dataclass
class TeamInvitation:
    """An affiliation offered with an invitation"""
    team_id: int
    access: Access

    def __post_init__(self):
        if not isinstance(self.access, Access):
            self.access = Access(self.access)


@dataclass(eq=False)
class InvitationBase(ABC):
    label: ClassVar[str] = 'Invitation'
    plural: ClassVar[str] = 'Invitations'

    email: str = ''
    invited_by: int = None
    teams: List[TeamInvitation] = field(default_factory=list)
    person_id: int | None = None


@dataclass(eq=False)
class InvitationInput(InvitationBase, LabeledModel):

    def __post_init__(self):
        self.email = (self.email or '').strip()
        if '@' not in self.email:
            raise IllegalOperationError("A valid email address is required to invite")
        if self.invited_by is None:
            raise IllegalOperationError("An invitation requires the inviting user")
        offers = [(team.team_id, team.access) for team in self.teams]
        if len(offers) != len(set(offers)):
            raise IllegalOperationError("Each access to a team can be offered once per invitation")

    def check_inviter(self, admin_teams: Set[int]) -> None:
        """Affiliations can only be offered for teams the inviter administers"""
        if not {team.team_id for team in self.teams}.issubset(admin_teams):
            raise UnauthorisedOperationError("Affiliations can only be offered to teams you administer")


@dataclass(eq=False)
class InvitationStored(InvitationBase, StoredModel, Aggregate):
    created_at: datetime | None = None
    expires_at: datetime | None = None

    @property
    def root(self) -> 'InvitationStored':
        return self

    @property
    def protected(self) -> str | None:
        return None

    def is_expired(self, now: datetime | None = None) -> bool:
        return self.expires_at is not None and self.expires_at <= (now or datetime.now(timezone.utc))

    def matches_email(self, email: str) -> bool:
        return self.email.casefold() == (email or '').strip().casefold()

    def accepted_teams(self, team_ids: Set[int] | None) -> List[TeamInvitation]:
        """
        The offered affiliations the invited user accepts: every access offered to each team they accept.
        Declining all of them is allowed.
        """
        team_ids = set(team_ids or [])
        unknown = team_ids - {team.team_id for team in self.teams}
        if unknown:
            raise IllegalOperationError(f"Teams were not offered with this invitation: {sorted(unknown)}")
        return sorted(
            (team for team in self.teams if team.team_id in team_ids),
            key=lambda team: (team.team_id, team.access.value)
        )

    def extend(self, days: int, now: datetime | None = None) -> None:
        self.expires_at = (now or datetime.now(timezone.utc)) + timedelta(days=days)
