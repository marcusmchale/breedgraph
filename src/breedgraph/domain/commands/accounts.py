from .base import Command
from typing import Optional, Set

class AddFirstAccount(Command):
    name: str
    fullname: Optional[str] = None
    email: str
    password_hash: str
    team_name: str
    team_fullname: Optional[str] = None

class AddAccount(Command):
    name: str
    fullname: Optional[str] = None
    email: str
    password_hash: str

class VerifyEmail(Command):
    token: str

class Login(Command):
    user: int

class AddTeam(Command):
    user: int
    name: str
    fullname: Optional[str] = None
    parent: Optional[int]

class RemoveTeam(Command):
    user: int
    team: int

class AddEmail(Command):
    user: int
    email: str

class RemoveEmail(Command):
    user: int
    email: str

class RequestAffiliation(Command):
    user: int
    team: int
    access: str

class ApproveAffiliation(Command):
    admin: int
    user: int
    team: int
    access: str
    heritable: bool

class RemoveAffiliation(Command):
    admin: int
    user: int
    team: int
    access: str
