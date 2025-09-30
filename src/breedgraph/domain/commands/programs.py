from typing import List
from .base import Command
from src.breedgraph.domain.model.time_descriptors import PyDT64

# Program Commands
class CreateProgram(Command):
    agent_id: int

    name: str
    fullname: str | None = None
    description: str | None = None

    contact_ids: List[int] = None
    reference_ids: List[int] = None


class UpdateProgram(Command):
    agent_id: int
    program_id: int

    name: str | None = None
    fullname: str | None = None
    description: str | None = None

    contact_ids: List[int] | None = None
    reference_ids: List[int] | None = None

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

    contact_ids: List[int] = None
    reference_ids: List[int] = None

class UpdateTrial(Command):
    agent_id: int
    trial_id: int

    name: str | None = None
    fullname: str | None = None
    description: str | None = None
    start: PyDT64 | None = None
    end: PyDT64 | None = None

    contact_ids: List[int] = None
    reference_ids: List[int] = None

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

    design_id: int | None = None
    licence_id: int | None = None

    dataset_ids: List[int] = None
    reference_ids: List[int] = None


class UpdateStudy(Command):
    agent_id: int
    study_id: int

    name: str | None = None
    fullname: str | None = None
    description: str | None = None
    practices: str | None = None
    start: PyDT64 | None = None
    end: PyDT64 | None = None

    design_id: int | None = None
    licence_id: int | None = None

    dataset_ids: List[int] = None
    reference_ids: List[int] = None

class DeleteStudy(Command):
    agent_id: int
    study_id: int