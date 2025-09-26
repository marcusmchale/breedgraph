from .base import Command
from src.breedgraph.domain.model.controls import Access

class CreateAccount(Command):
    name: str
    fullname: str|None = None
    email: str
    password_hash: str

class UpdateUser(Command):
    user_id: int
    name: str|None = None
    fullname: str|None = None
    email: str|None = None
    password_hash: str|None = None

class VerifyEmail(Command):
    token: str

class Login(Command):
    user_id: int

class AddEmail(Command):
    user_id: int
    email: str

class RemoveEmail(Command):
    user_id: int
    email: str

class SetOntologyRole(Command):
    agent_id: int

    user_id: int
    role: str

class RequestAffiliation(Command):
    user_id: int
    team_id: int
    access: Access
    heritable: bool

class ApproveAffiliation(Command):
    agent_id: int

    user_id: int
    team_id: int
    access: Access
    heritable: bool

class RemoveAffiliation(Command):
    agent_id: int

    user_id: int
    team_id: int
    access: Access

class RevokeAffiliation(Command):
    agent_id: int

    user_id: int
    team_id: int
    access: Access
