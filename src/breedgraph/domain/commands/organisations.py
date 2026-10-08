from pydantic import BaseModel

from .base import Command

class LegalEntity(BaseModel):
    legal_name: str
    privacy_contact: str
    terms_version: str  # the version of the data processing terms shown to and accepted by the user

class CreateTeam(Command):
    agent_id: int

    name: str
    fullname: str|None = None
    parent: int|None
    legal_entity: LegalEntity | None = None  # only for an organisation root, i.e. without a parent

class UpdateTeam(Command):
    agent_id: int
    team_id: int

    name: str|None = None
    fullname: str|None = None

class DeclareLegalEntity(Command):
    agent_id: int
    team_id: int
    legal_entity: LegalEntity

class WithdrawLegalEntity(Command):
    agent_id: int
    team_id: int

class DeleteTeam(Command):
    agent_id: int
    team_id: int

