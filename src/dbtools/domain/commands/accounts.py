from .base import Command
from typing import Optional


class AddAccount(Command):
    team_name: str
    team_fullname: Optional[str]
    username: str
    fullname: str
    password_hash: str
    email: str


class Login(Command):
    username: str


class AddEmail(Command):
    user_id: int
    email: str


class RemoveEmail(Command):
    user_id: int
    email: str


class ConfirmUser(Command):
    token: str


class SetAffiliation(Command):
    user_id: int
    team_name: str
    team_fullname: str
    level: int
