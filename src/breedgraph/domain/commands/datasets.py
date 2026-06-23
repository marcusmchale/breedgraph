from .base import Command

class SubmitRecords(Command):
    agent_id: int
    submission_id: str

class UpdateRecords(Command):
    agent_id: int
    submission_id: str

class RemoveRecords(Command):
    agent_id: int
    dataset_id: int
    record_ids: list[int]
