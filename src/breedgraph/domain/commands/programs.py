from typing import List
from .base import Command
from src.breedgraph.domain.model.time_descriptors import PyDT64
from src.breedgraph.domain.model.controls import ReadRelease

# Program Commands
class CreateProgram(Command):
    user: int  # Required for ControlledRepository
    name: str
    fullname: str | None = None
    description: str | None = None
    contacts: List[int] = []
    references: List[int] = []
    release: str = ReadRelease.REGISTERED.name


class UpdateProgram(Command):
    user: int  # Required for ControlledRepository
    program: int
    name: str | None = None
    fullname: str | None = None
    description: str | None = None
    contacts: List[int] | None = None
    references: List[int] | None = None
    release: str | None = None

class DeleteProgram(Command):
    user: int  # Required for ControlledRepository
    program: int

# Trial Commands
class CreateTrial(Command):
    user: int  # Required for ControlledRepository
    program: int  # Only needed for creation to know which program to add to
    name: str
    fullname: str | None = None
    description: str | None = None
    start: PyDT64 | None = None
    end: PyDT64 | None = None
    contacts: List[int] = []
    references: List[int] = []
    release: str = ReadRelease.REGISTERED.name


class UpdateTrial(Command):
    user: int  # Required for ControlledRepository
    trial: int  # Unique ID is sufficient
    name: str | None = None
    fullname: str | None = None
    description: str | None = None
    start: PyDT64 | None = None
    end: PyDT64 | None = None
    contacts: List[int] | None = None
    references: List[int] | None = None
    release: str | None = None


class DeleteTrial(Command):
    user: int  # Required for ControlledRepository
    trial: int  # Unique ID is sufficient


# Study Commands
class CreateStudy(Command):
    user: int  # Required for ControlledRepository
    trial: int  # Only needed for creation to know which trial to add to
    name: str
    fullname: str | None = None
    description: str | None = None
    external_id: str | None = None
    practices: str | None = None
    start: PyDT64 | None = None
    end: PyDT64 | None = None
    factors: List[int] = []
    observations: List[int] = []
    design: int | None = None
    licence: int | None = None
    references: List[int] = []
    release: str = ReadRelease.REGISTERED.name


class UpdateStudy(Command):
    user: int  # Required for ControlledRepository
    study: int  # Unique ID is sufficient
    name: str | None = None
    fullname: str | None = None
    description: str | None = None
    external_id: str | None = None
    practices: str | None = None
    start: PyDT64 | None = None
    end: PyDT64 | None = None
    factors: List[int] | None = None
    observations: List[int] | None = None
    design: int | None = None
    licence: int | None = None
    references: List[int] | None = None
    release: str | None = None


class DeleteStudy(Command):
    user: int  # Required for ControlledRepository
    study: int  # Unique ID is sufficient