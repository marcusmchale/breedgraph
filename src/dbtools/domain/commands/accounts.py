from .base import Command


class Initialise(Command):
    team_name: str
    team_fullname: str
    username: str
    user_fullname: str
    password_hash: str
    email: str


class Login(Command):
    username: str


class AddTeam(Command):
    name: str
    fullname: str
    admin_username_lower: str


class AddEmail(Command):
    admin_username_lower: str
    user_email: str


class RemoveEmail(Command):
    admin_username_lower: str
    user_email: str


class AddAccount(Command):
    username: str
    fullname: str
    password_hash: str
    email: str
    team_name: str


class ConfirmUser(Command):
    token: str


class AddAffiliation(Command):
    username_lower: str
    team_name: str


class SetAffiliationLevel(Command):
    admin_username_lower: str
    username_lower: str
    team_name: str
    level: int
