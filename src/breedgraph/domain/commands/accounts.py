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

class RequestRead(RequestAffiliation):
    pass

class RequestWrite(RequestAffiliation):
    pass

class RequestAdmin(RequestAffiliation):
    pass

class SetAffiliation(Command):
    admin: int
    user: int
    team: int

class AddRead(SetAffiliation):
    heritable: bool

class RemoveRead(SetAffiliation):
    pass

class AddWrite(SetAffiliation):
    pass
class RemoveWrite(SetAffiliation):
    pass

class AddAdmin(SetAffiliation):
    pass
class RemoveAdmin(SetAffiliation):
    pass
