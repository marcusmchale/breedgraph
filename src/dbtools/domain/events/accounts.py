from .base import Event


class EmailAdded(Event):
    email: str


class AccountAdded(Event):
    username_lower: str


class AffiliationConfirmed(Event):
    username_lower: str
    team_name: str


class AdminGranted(Event):
    username_lower: str
    team_name: str
