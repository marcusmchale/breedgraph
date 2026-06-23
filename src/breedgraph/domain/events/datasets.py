from .base import Event

class RecordsSubmitted(Event):
    agent_id: int
    submission_id: str

class RecordUpdatesSubmitted(Event):
    agent_id: int
    submission_id: str
