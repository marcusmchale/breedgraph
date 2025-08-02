import logging

from .base import LabeledModel
from .controls import ControlledModel, ControlledAggregate, Access, Controller

from typing import List, Set, ClassVar, Dict

logger = logging.getLogger(__name__)

class PersonBase(LabeledModel):
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

class PersonInput(PersonBase):
    pass

class PersonStored(PersonBase, ControlledModel, ControlledAggregate):

    @property
    def controlled_models(self) -> List[ControlledModel]:
        return [self]

    @property
    def root(self) -> ControlledModel:
        return self

    @property
    def protected(self) -> str | None:
        return None

    def redacted(
            self,
            controllers: Dict[str, Dict[int, Controller]],
            user_id=None,
            read_teams=None
    ) -> 'PersonStored|None':
        controller = controllers['Person'][self.id]

        if read_teams is None:
            read_teams = set()

        if controller.has_access(Access.READ, user_id, read_teams):
            return self
        else:
            if user_id is None:
                return None

            redacted: PersonStored = self.model_copy(
                deep=True,
                update = {
                    'name' : self._redacted_str,
                    'fullname' : self._redacted_str if self.fullname is not None else None,
                    'email' : self._redacted_str if self.email is not None else None,
                    'phone' : self._redacted_str if self.phone is not None else None,
                    'orcid' : self._redacted_str if self.orcid is not None else None,
                    'description' : self._redacted_str if self.description is not None else None,
                    'user' : None,
                    'teams' : list(),
                    'locations' : list(),
                    'roles' : list(),
                    'titles' : list()
                }
            )
            return redacted
