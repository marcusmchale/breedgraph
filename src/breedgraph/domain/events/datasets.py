from .base import Event
from breedgraph.domain.model.controls import ReadRelease


class DatasetSubmitted(Event):
    agent_id: int
    write_team: int | None = None
    release: ReadRelease = ReadRelease.PRIVATE

    submission_id: str

class DatasetRecordsSubmitted(Event):
    agent_id: int
    submission_id: str

class DatasetUpdateSubmitted(Event):
    agent_id: int
    submission_id: str
