from typing import List
from .base import Command
from src.breedgraph.domain.model.time_descriptors import PyDT64

# Program Commands
class CreateProgram(Command):
    agent_id: int

    name: str
    fullname: str | None = None
    description: str | None = None

    contacts: List[int] = None
    references: List[int] = None


class UpdateProgram(Command):
    agent_id: int
    program_id: int

    name: str | None = None
    fullname: str | None = None
    description: str | None = None

    contacts: List[int] | None = None
    references: List[int] | None = None

class DeleteProgram(Command):
    agent_id: int
    program_id: int

# Trial Commands
class CreateTrial(Command):
    agent_id: int
    program_id: int

    name: str
    fullname: str | None = None
    description: str | None = None
    start: PyDT64 | None = None
    end: PyDT64 | None = None

    contacts: List[int] = None
    references: List[int] = None

class UpdateTrial(Command):
    agent_id: int
    trial_id: int

    name: str | None = None
    fullname: str | None = None
    description: str | None = None
    start: PyDT64 | None = None
    end: PyDT64 | None = None

    contacts: List[int] = None
    references: List[int] = None

class DeleteTrial(Command):
    agent_id: int
    trial_id: int


# Study Commands
class CreateStudy(Command):
    agent_id: int
    trial_id: int

    name: str
    fullname: str | None = None
    description: str | None = None
    practices: str | None = None
    start: PyDT64 | None = None
    end: PyDT64 | None = None

    datasets: List[int] = None
    design: int | None = None
    licence: int | None = None
    references: List[int] = None


class UpdateStudy(Command):
    agent_id: int
    study_id: int

    name: str | None = None
    fullname: str | None = None
    description: str | None = None
    practices: str | None = None
    start: PyDT64 | None = None
    end: PyDT64 | None = None

    datasets: List[int] = None
    design: int | None = None
    licence: int | None = None
    references: List[int] = None


class DeleteStudy(Command):
    agent_id: int
    study_id: int