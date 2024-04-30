from .base import Event

class EmailAdded(Event):
    email: str

class EmailRemoved(Event):
    email: str

class AccountAdded(Event):
    user: int

class EmailVerified(Event):
    user: int

class ReadRequested(Event):
    user: int
    team: int

class ReadAdded(Event):
    user: int
    team: int

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