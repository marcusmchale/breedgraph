from breedgraph.domain.model.controls import ReadRelease

from .base import Command


class CreateDataset(Command):
    agent_id: int
    write_team: int | None = None
    release: ReadRelease = ReadRelease.PRIVATE

    submission_id: str

class AddRecords(Command):
    agent_id: int
    submission_id: str

class UpdateDataset(Command):
    agent_id: int
    submission_id: str

class RemoveRecords(Command):
    agent_id: int
    dataset_id: int
    record_ids: list[int]
