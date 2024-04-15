from .base import Event

class EmailAdded(Event):
    email: str

class EmailRemoved(Event):
    email: str

class AccountAdded(Event):
    user_id: int

class EmailVerified(Event):
    user_id: int

class ReadRequested(Event):
    user_id: int
    team_id: int

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