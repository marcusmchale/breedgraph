from .base import Event

class DatasetSubmitted(Event):
    agent_id: int
    submission_id: str

class DatasetRecordsSubmitted(Event):
    agent_id: int
    submission_id: str

class DatasetUpdateSubmitted(Event):
    agent_id: int
    submission_id: str
