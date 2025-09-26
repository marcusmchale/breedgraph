from .base import Command
from typing import Optional
class CreateTeam(Command):
    agent_id: int

    name: str
    fullname: Optional[str] = None
    parent: Optional[int]

class UpdateTeam(Command):
    agent_id: int
    team_id: int

    name: Optional[str] = None
    fullname: Optional[str] = None

class DeleteTeam(Command):
    agent_id: int
    team_id: int

