from breedgraph.domain.model.time_descriptors import PyDT64
from breedgraph.domain.model.controls import ReadRelease
from breedgraph.domain.model.programs import GroupingScope

from .base import Command


# Program Commands
class CreateProgram(Command):
    agent_id: int
    write_team: int | None = None
    release: ReadRelease = ReadRelease.PRIVATE

    name: str
    fullname: str | None = None
    description: str | None = None

    contact_ids: list[int] | None = None
    reference_ids: list[int] | None = None


class UpdateProgram(Command):
    agent_id: int
    program_id: int

    name: str | None = None
    fullname: str | None = None
    description: str | None = None

    contact_ids: list[int] | None = None
    reference_ids: list[int] | None = None

class DeleteProgram(Command):
    agent_id: int
    program_id: int

# Trial Commands
class CreateTrial(Command):
    agent_id: int
    write_team: int | None = None
    release: ReadRelease = ReadRelease.PRIVATE

    program_id: int

    name: str
    fullname: str | None = None
    description: str | None = None
    start: PyDT64 | None = None
    end: PyDT64 | None = None

    contact_ids: list[int] | None = None
    reference_ids: list[int] | None = None

class UpdateTrial(Command):
    agent_id: int
    trial_id: int

    name: str | None = None
    fullname: str | None = None
    description: str | None = None
    start: PyDT64 | None = None
    end: PyDT64 | None = None

    contact_ids: list[int] | None = None
    reference_ids: list[int] | None = None

class DeleteTrial(Command):
    agent_id: int
    trial_id: int

# Study Commands
class CreateStudy(Command):
    agent_id: int
    write_team: int | None = None
    release: ReadRelease = ReadRelease.PRIVATE

    trial_id: int

    name: str
    fullname: str | None = None
    description: str | None = None
    practices: str | None = None
    start: PyDT64 | None = None
    end: PyDT64 | None = None

    design_id: int | None = None
    licence_id: int | None = None

    reference_ids: list[int] | None = None


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

    reference_ids: list[int] | None = None


class DeleteStudy(Command):
    agent_id: int
    study_id: int


# Grouping commands
class CreateGrouping(Command):
    agent_id: int

    study_id: int
    type_id: int
    name: str
    scope: GroupingScope
    dataset_scopes: list[set[int]] | None = None

class UpdateGrouping(Command):
    agent_id: int

    grouping_id: int

    type_id: int | None = None
    name: str | None = None
    dataset_scopes: list[set[int]] | None = None

class DeleteGrouping(Command):
    agent_id: int
    grouping_id: int

class MergeDatasetScope(Command):
    agent_id: int
    grouping_id: int

    dataset_ids: set[int]


