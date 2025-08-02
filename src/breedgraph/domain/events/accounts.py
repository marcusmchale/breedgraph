from .base import Event

class AccountCreated(Event):
    user: int

class EmailAdded(Event):
    email: str

class EmailVerified(Event):
    user: int

class AffiliationRequested(Event):
    user: int
    team: int
    access: str

class AffiliationApproved(Event):
    user: int
    team: int
    access: str

class PasswordChangeRequested(Event):
    email: str

class EmailChangeRequested(Event):
    user: int
    email: str