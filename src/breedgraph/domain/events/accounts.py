from datetime import datetime

from .base import Event
from breedgraph.domain.model.controls import Access


class AccountCreated(Event):
    user_id: int

class InvitationIssued(Event):
    invitation_id: int

class EmailVerified(Event):
    user_id: int

class AccountDeleted(Event):
    user_id: int
    deleted_at: datetime
    created_at: datetime | None = None  # when the account was created, so a replay deletes this account and no other

class AffiliationRequested(Event):
    user_id: int
    team_id: int
    access: Access

class AffiliationApproved(Event):
    user_id: int
    team_id: int
    access: Access

class PasswordChangeRequested(Event):
    email: str

class EmailChangeRequested(Event):
    user_id: int
    email: str