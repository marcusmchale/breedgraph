import logging

from pydantic import BaseModel
from time_descriptors import PyDT64
from datetime import datetime


from src.breedgraph.domain.model.base import StoredModel, Aggregate
from src.breedgraph.domain.model.controls import ControlledModel, ControlledAggregate, Access
from src.breedgraph.domain.model.references import ExternalReference, FileReference


from typing import List, Set

logger = logging.getLogger(__name__)


class StudyBase(BaseModel):
    """
    This is like the Study concept
    https://isa-specs.readthedocs.io/en/latest/isamodel.html
    """
    name: str
    fullname: str|None = None
    description: str|None = None

    external_id: str|None = None  # a permanent external identifier, should we make this UUID?

    # MIAPPE V1.1 (DM-28) General description of the cultural practices associated with the study.
    practices: str|None = None

    start: PyDT64 | None
    end: PyDT64 | None

    # MIAPPE DM60: exposure or condition that is being tested.
    factors: List[int]  # list of StudyTerm IDs, these terms should be linked to Parameter or Event in the ontology
    observations: List[int]  # list of StudyTerm IDs. These should be linked to Variable in the ontology

    # Germplasm, Location are defined for units, to retrieve from there for read operations
    # Units in turn are accessed through factors/observations
    design: int | None  # Reference to Design in Ontology

    licence: int | None  # A single LegalReference for usage of data associated with factors/observations in this experiment

    references: List[int] # list of other references by IDs


class StudyInput(StudyBase):
    pass

class StudyStored(StudyBase, ControlledModel):

    def redacted(self) -> 'ControlledModel':
        return self.model_copy(deep=True, update={
            'name': self.redacted_str,
            'fullname': self.redacted_str if self.fullname is not None else None,
            'description': self.redacted_str if self.description is not None else None,
            'external_id': self.redacted_str if self.external_id is not None else None,
            'practices': self.redacted_str if self.practices is not None else None,
            'start': None,
            'end': None,
            'factors': list(),
            'observations': list(),
            'design': None,
            'licence': None,
            'references': list()
        })


class TrialBase(BaseModel):
    """
    This is like the Trial concept in BrAPI,
    But using the more widespread terminology from ISA
    https://isa-specs.readthedocs.io/en/latest/isamodel.html
    """

    name: str
    fullname: str|None = None
    description: str|None = None

    start: datetime
    end: None | datetime

    studies: dict[int, StudyInput|StudyStored]  # keyed by ID or assigned a temporary ID for inputs

    contacts: List[int] # list of Person by ID suitable to contact for queries about this study.
    publications: List[int]  # list of PublicationReference by ID
    references: List[int]  # list of other reference by ID

class TrialInput(TrialBase):
    pass

class TrialStored(TrialBase, ControlledModel):

    def redacted(self) -> 'TrialStored':

        return self.model_copy(deep=True, update={
            'name': self.redacted_str,
            'fullname': self.redacted_str if self.fullname is not None else None,
            'description': self.redacted_str if self.description is not None else None,
            'start': None,
            'end': None,
            'factors': list(),
            'observations': list(),
            'design': None,
            'licence': None,
            'references': list()
        })


class ProgramBase(BaseModel):
    name: str
    fullname: str|None = None
    description: str|None = None

    leader: int  # PersonStored by ID

    trials: dict[int, TrialInput|TrialStored] # keyed by ID or assigned a temporary ID for inputs
    references: List[int]  # list of reference IDs

class ProgramInput(ProgramBase):
    pass

class ProgramStored(ProgramBase, ControlledModel, ControlledAggregate):

    @property
    def controlled_models(self) -> List[ControlledModel]:
        # We have distinct controls on trials and nested studies.
        # Trials may then be shared without sharing associated studies
        trials = list(self.trials.values())
        studies = [study for trial in trials for study in trial.studies.values()]
        references = [self.references]

        return trials + studies + references

    @property
    def root(self) -> StoredModel:
        return self

    @property
    def protected(self) -> str | None:
        if self.trials:
            return "Programs with established trials may not be removed"

    def redacted(self, user_id: int = None, read_teams: Set[int] = None) -> 'ProgramStored':
        if read_teams is None:
            read_teams = set()

        redacted = self.model_copy(deep=True)

        for trial_key, trial in self.trials.items():
            if not trial.controller.has_access(Access.READ, user_id, read_teams):
                if user_id is None:
                    redacted.trials.pop(trial_key)
                else:
                    redacted.trials[trial_key] = trial.redacted()
            else:
                for study_key, study in trial.studies.values():
                    if not study.controller.has_access(Access.READ, user_id, read_teams):
                        if user_id is None:
                            redacted.trials[trial_key].pop(study_key)
                        else:
                            redacted.trials[trial_key] = study.redacted()

        if user_id is None:
            redacted.references[:] = [
                r for r in redacted.references if r.controller.has_access(Access.READ, user_id, read_teams)
            ]
        else:
            redacted.references[:] = [
                r if r.controller.has_access(Access.READ, user_id, read_teams) else r.redacted() for r in redacted.references
            ]

        return redacted

