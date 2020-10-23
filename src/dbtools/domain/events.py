from dataclasses import dataclass


@dataclass
class Event:
	pass


@dataclass
class EmailAdded(Event):
	email: str


@dataclass
class AccountAdded(Event):
	username_lower: str


@dataclass
class AffiliationConfirmed(Event):
	username_lower: str
	team_name: str


@dataclass
class AdminGranted(Event):
	username_lower: str
	team_name: str

