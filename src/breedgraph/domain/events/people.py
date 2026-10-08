from datetime import datetime

from .base import Event


class PersonErased(Event):
    person_id: int
    erased_at: datetime
