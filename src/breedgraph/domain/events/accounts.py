from .base import Event

class AccountAdded(Event):
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

#
#class AffiliationConfirmed(Event):
#    user_id: int
#    team_name: str
#
#
#class AdminGranted(Event):
#    user_id: int
#    team_name: str
#