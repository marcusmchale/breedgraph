from .base import Command

class CreateTeam(Command):
    agent_id: int

    name: str
    fullname: str|None = None
    parent: int|None

class UpdateTeam(Command):
    agent_id: int
    team_id: int

    name: str|None = None
    fullname: str|None = None

class DeleteTeam(Command):
    agent_id: int
    team_id: int

