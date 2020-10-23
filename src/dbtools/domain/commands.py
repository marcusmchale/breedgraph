from dataclasses import dataclass


@dataclass
class Command:
	pass


@dataclass
class AddEmail(Command):
	admin_username_lower: str
	user_email: str


@dataclass
class RemoveEmail(Command):
	admin_username_lower: str
	user_email: str


@dataclass
class AddAccount(Command):
	username: str
	fullname: str
	password_hash: str
	user_email: str
	team_name: str


@dataclass
class ConfirmUser(Command):
	token: str


@dataclass
class AddAffiliation(Command):
	username_lower: str
	team_name: str


@dataclass
class SetAffiliationLevel(Command):
	admin_username_lower: str
	username_lower: str
	team_name: str
	level: int
