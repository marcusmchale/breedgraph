import logging

from pydantic import BaseModel

from src.breedgraph.domain.model.base import StoredModel, LabeledModel
from src.breedgraph.domain.model.controls import ControlledModel, ControlledAggregate, Access, Controller
from src.breedgraph.domain.model.time_descriptors import PyDT64

from typing import List, Set, ClassVar, Dict

logger = logging.getLogger(__name__)


class StudyBase(LabeledModel):
    label: ClassVar[str] = 'Study'
    plural: ClassVar[str] = 'Studies'

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

    start: PyDT64 | None = None
    end: PyDT64 | None = None

    # MIAPPE DM60: exposure or condition that is being tested.
    factors: List[int] = list() # list of DataSet IDs, these would typically be linked to Parameter or Event in the ontology
    observations: List[int] = list()  # list of DataSet IDs. These would typically be linked to a Variable in the ontology

    # Germplasm, Location are defined for units, to retrieve from there for read operations
    # Units in turn are accessed through factors/observations
    design: int | None = None  # Reference to Design in Ontology

    licence: int | None = None  # A single LegalReference for usage of data associated with factors/observations in this experiment

    references: List[int] = list() # list of other references by IDs


class StudyInput(StudyBase):
    pass

class StudyStored(StudyBase, ControlledModel):

    def redacted(
            self,
            controller: Controller,
            user_id = None,
            read_teams = None
    ) -> 'ControlledModel':
        if controller.has_access(Access.READ, user_id, read_teams):
            return self

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


class TrialBase(LabeledModel):
    """
    This is like the Trial concept in BrAPI,
    But using the more widespread terminology from ISA
    https://isa-specs.readthedocs.io/en/latest/isamodel.html
    """
    label: ClassVar[str] = 'Trial'
    plural: ClassVar[str] = 'Trials'

    name: str
    fullname: str|None = None
    description: str|None = None

    start: PyDT64|None = None
    end: PyDT64|None = None

    contacts: List[int] = list() # list of Person by ID suitable to contact for queries about this study.
    references: List[int] = list()  # list of reference by ID

class TrialInput(TrialBase):
    pass

class TrialStored(TrialBase, ControlledModel):

    studies: Dict[int, StudyStored|StudyInput] = dict() # keyed by ID or assigned a temporary ID for inputs

    def redacted(
            self,
            controller: Controller,
            user_id=None,
            read_teams=None
    ) -> 'TrialStored':

        if controller.has_access(Access.READ, user_id, read_teams):
            return self

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

    def add_study(self, study: StudyInput):
        temp_key = -len(self.studies) - 1
        self.studies[temp_key] = study

class ProgramBase(LabeledModel):
    label: ClassVar[str] = 'Program'
    plural: ClassVar[str] = 'Programs'

    name: str
    fullname: str|None = None
    description: str|None = None
    contacts: List[int] = list() # list of Person by ID suitable to contact for queries about this program.
    references: List[int] = list()  # list of reference IDs

class ProgramInput(ProgramBase):
    pass

class ProgramStored(ProgramBase, ControlledModel, ControlledAggregate):

    trials: Dict[int, TrialStored|TrialInput] = dict()  # keyed by ID or assigned a temporary ID for inputs

    @property
    def controlled_models(self) -> List[ControlledModel]:
        # We have distinct controls on trials and nested studies.
        # Trials may then be shared without sharing associated studies
        trials = [i for i in self.trials.values() if isinstance(i, ControlledModel)]
        studies = [
            study for trial in trials
            if hasattr(trial, 'studies')
            for study in trial.studies.values()
            if isinstance(study, ControlledModel)
        ]
        return [self] + trials + studies

    @property
    def root(self) -> StoredModel:
        return self

    @property
    def protected(self) -> str | None:
        if self.trials:
            return "Programs with established trials may not be removed"
        return None

    def redacted(
            self,
            controllers: Dict[str, Dict[int, Controller]],
            user_id=None,
            read_teams=None
    ) -> 'ProgramStored':

        program_controller = controllers['Program'][self.id]
        if program_controller.has_access(Access.READ, user_id, read_teams):
            aggregate = self

        else:
            aggregate = self.model_copy(
                deep=True,
                update={
                    'name': self.redacted_str,
                    'fullname': None,
                    'description': None,
                    'contacts': list(),
                    'references': list()
                }
            )

        for trial_key, trial in self.trials.items():
            if not controllers['Trial'][trial_key].has_access(Access.READ, user_id, read_teams):
                if user_id is None:
                    aggregate.trials.pop(trial_key)
                else:
                    aggregate.trials[trial_key] = trial.redacted(
                        controller=controllers['Trial'][trial_key],
                        user_id=user_id,
                        read_teams=read_teams
                    )

            for study_key, study in trial.studies.items():
                if not controllers['Study'][study_key].has_access(Access.READ, user_id, read_teams):
                    if user_id is None:
                        aggregate.trials[trial_key].pop(study_key)
                    else:
                        aggregate.trials[trial_key][study_key] = study.redacted(
                            controller=controllers['Study'][study_key],
                            user_id=user_id,
                            read_teams=read_teams
                        )

        return aggregate

    def add_trial(self, trial: TrialInput):
        temp_key = -len(self.trials) - 1
        self.trials[temp_key] = trial

    def to_output_map(self):
        return {
            self.id: ProgramOutput(**self.model_dump())
        }

class ProgramOutput(ProgramStored):
    # returning the ProgramStored, just giving new type in case of future requirements
    pass


