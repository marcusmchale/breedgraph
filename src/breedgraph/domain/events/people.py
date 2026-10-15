from datetime import datetime

from .base import Event


class PersonErased(Event):
    person_id: int
    erased_at: datetime
    recorded_at: datetime | None = None  # when the Person was created, so a replay erases this Person and no other


class PersonClaimRequested(Event):
    person_id: int
    user_id: int


class PersonLinked(Event):
    person_id: int
    user_id: int
