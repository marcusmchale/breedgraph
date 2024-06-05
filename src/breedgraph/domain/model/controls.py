from pydantic import BaseModel, Field
from enum import IntEnum
from datetime import datetime
from typing import List
from src.breedgraph.domain.model.accounts import AccountStored

class Release(IntEnum):
    PRIVATE = 0  # accessible only to users with an authorised affiliation to the controller
    REGISTERED = 1 # accessible to any registered user
    PUBLIC = 2  # accessible to non-registered users # todo


class Control(BaseModel):
    team: int  # team id
    release: Release
    time: datetime

class WriteStamp(BaseModel):
    user: int  # user id
    time: datetime

class RecordController(BaseModel):
    controls: List[Control]
    writes: List[WriteStamp] = Field(frozen=True) # for auditing

    @property
    def controllers(self):
        return [c.team for c in self.controls]

    @property
    def release(self):
        return min([c.release for c in self.controls])

    @property
    def created(self):
        return min([w.time for w in self.writes])

    @property
    def updated(self):
        return max([w.time for w in self.writes])

    def can_read(self, account: AccountStored|None) -> bool:
        for control in self.controls:
            if control.release == Release.PUBLIC:
                return True
            elif account is not None:
                if control.release == Release.REGISTERED:
                    return True
                elif control.release == Release.PRIVATE and control.team in account.reads:
                    return True
        return False

    def can_curate(self, account: AccountStored|None) -> bool:
        for control in self.controls:
            if control.team in account.curates:
                return True
        return False

    def can_release(self, account: AccountStored|None) -> bool:
        for control in self.controls:
            if control.team in account.admins:
                return True
        return False