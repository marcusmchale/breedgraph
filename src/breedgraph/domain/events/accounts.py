from .base import Event

class AccountCreated(Event):
    user_id: int

class EmailAdded(Event):
    email: str

class EmailVerified(Event):
    user_id: int

class AffiliationRequested(Event):
    user_id: int
    team_id: int
    access: str

class AffiliationApproved(Event):
    user_id: int
    team_id: int
    access: str

class PasswordChangeRequested(Event):
    email: str

class EmailChangeRequested(Event):
    user_id: int
    email: str