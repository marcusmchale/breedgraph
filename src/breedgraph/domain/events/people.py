from datetime import datetime

from .base import Event


class PersonErased(Event):
    person_id: int
    erased_at: datetime


class PersonClaimRequested(Event):
    person_id: int
    user_id: int


class PersonLinked(Event):
    person_id: int
    user_id: int
