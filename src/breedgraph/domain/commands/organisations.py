from .base import Command
from typing import Optional
class AddTeam(Command):
    user: int
    name: str
    fullname: Optional[str] = None
    parent: Optional[int]

class RemoveTeam(Command):
    user: int
    team: int

class EditTeam(Command):
    user: int
    team: int
    name: Optional[str] = None
    fullname: Optional[str] = None