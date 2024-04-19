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
    user_id: int

class AddTeam(Command):
    user_id: int
    name: str
    fullname: Optional[str] = None
    parent_id: Optional[int]

class AddEmail(Command):
    user_id: int
    email: str

class RemoveEmail(Command):
    user_id: int
    email: str

class RequestAffiliation(Command):
    user_id: int
    team_id: int

class RequestRead(RequestAffiliation):
    pass

class RequestWrite(RequestAffiliation):
    pass

class RequestAdmin(RequestAffiliation):
    pass

class SetAffiliation(Command):
    admin_id: int
    user_id: int
    team_id: int
    heritable: bool

class AddRead(SetAffiliation):
    pass
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
