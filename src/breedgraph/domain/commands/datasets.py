from .base import Command

class CreateDataset(Command):
    agent_id: int
    submission_id: str

class UpdateDataset(Command):
    agent_id: int
    key: str

class AddRecords(Command):
    agent_id: int
    key: str

class RemoveRecords(Command):
    agent_id: int
    dataset_id: int
    record_ids: list[int]
