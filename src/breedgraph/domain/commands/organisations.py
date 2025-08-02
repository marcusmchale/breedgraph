from .base import Command
from typing import Optional
class CreateTeam(Command):
    user: int
    name: str
    fullname: Optional[str] = None
    parent: Optional[int]

class UpdateTeam(Command):
    user: int
    team: int
    name: Optional[str] = None
    fullname: Optional[str] = None

class DeleteTeam(Command):
    user: int
    team: int

