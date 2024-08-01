import logging

from pydantic import BaseModel

from .accounts import AccountStored
from .controls import ControlledModel, ControlledAggregate, ReadRelease

from typing import List, ClassVar

logger = logging.getLogger(__name__)


class PersonBase(BaseModel):
    label: ClassVar[str] = 'Person'
    plural: ClassVar[str] = 'People'

    name: str
    fullname: None|str = None

    # contact details
    email: None|str = None
    mail: None|str = None
    phone: None|str = None
    orcid: None|str = None

    description: None | str = None  # e.g. Titles etc. if not captured by Role

    user: int | None = None  # Optional ID for the corresponding user
    teams: List[int] | None = None  # references to stored Team ID
    locations: List[int] | None = None  # references to stored Location

    roles: List[int]|None = None  # references to PersonRole in ontology
    titles: List[int]|None = None  # references to PersonTitle in ontology

class PersonInput(PersonBase, ControlledModel):
    pass

class PersonStored(PersonBase, ControlledModel, ControlledAggregate):

    @property
    def root(self) -> ControlledModel:
        return self

    @property
    def protected(self) -> str | None:
        return None

    def redacted(self, account: AccountStored):
        if not self.controller.can_read(account):

            if not account:
                return None

            person: PersonStored = self.model_copy()

            person.name = self._redacted_str
            person.fullname = None
            person.email = None
            person.mail = None
            person.phone = None
            person.orcid = None
            person.description = None
            person.user = None
            person.teams = None
            person.locations = None
            person.roles = None
            person.titles = None

            return person

        else:
            return self