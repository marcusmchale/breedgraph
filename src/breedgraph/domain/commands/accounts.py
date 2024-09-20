from .base import Command
from typing import Optional

class AddAccount(Command):
    name: str
    fullname: str|None = None
    email: str
    password_hash: str

class UpdateUser(Command):
    user: int
    name: str|None = None
    fullname: str|None = None
    email: str|None = None
    password_hash: str|None = None

class VerifyEmail(Command):
    token: str

class Login(Command):
    user: int

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
    agent: int
    user: int
    team: int
    access: str
    heritable: bool

class RemoveAffiliation(Command):
    agent: int
    user: int
    team: int
    access: str

class RevokeAffiliation(Command):
    agent: int
    user: int
    team: int
    access: str