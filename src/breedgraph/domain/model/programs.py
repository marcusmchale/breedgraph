from abc import ABC
from dataclasses import dataclass, field, replace
from src.breedgraph.service_layer.tracking.wrappers import asdict
from numpy import datetime64

from src.breedgraph.domain.model.base import StoredModel, LabeledModel
from src.breedgraph.domain.model.controls import ControlledModel, ControlledAggregate, Access, Controller


from typing import List, Set, ClassVar, Dict, Any, Self

import logging
logger = logging.getLogger(__name__)

@dataclass
class StudyBase(ABC):
    label: ClassVar[str] = 'Study'
    plural: ClassVar[str] = 'Studies'

    """
    This is like the Study concept
    https://isa-specs.readthedocs.io/en/latest/isamodel.html
    """
    name: str = None
    fullname: str|None = None
    description: str|None = None

    # MIAPPE V1.1 (DM-28) General description of the cultural practices associated with the study.
    practices: str|None = None

    start: datetime64|None = None
    end: datetime64|None = None

    datasets: List[int] = field(default_factory=list)  # list of DataSet IDs.

    # Germplasm, Location are defined for units, to retrieve from there for read operations
    # Units in turn are accessed through factors/observations
    design: int | None = None  # Reference to Design in Ontology

    licence: int | None = None  # A single LegalReference for usage of data associated with factors/observations in this experiment

    references: List[int] = field(default_factory=list) # list of other references by IDs

@dataclass
class StudyInput(StudyBase, LabeledModel):
    pass

@dataclass
class StudyStored(StudyBase, ControlledModel):

    def redacted(
            self,
            controller: Controller,
            user_id = None,
            read_teams = None
    ) -> Self:
        if controller.has_access(Access.READ, user_id, read_teams):
            return self

        return replace(
            self,
            name = self.redacted_str,
            fullname = self.fullname and self.redacted_str,
            description = self.description and self.redacted_str,
            practices = self.practices and self.redacted_str,
            start = None,
            end = None,
            datasets = list(),
            design = None,
            licence = None,
            references = list()
        )

@dataclass
class StudyOutput(StudyBase):
    # MIAPPE DM60: exposure or condition that is being tested.
    factors: List[int] = field(default_factory=list)  # Factors in the ontology with datasets that vary across subjects within the study
    variables: List[int] = field(default_factory=list)  # Variables in the ontology with datasets that vary across subjects within the study

@dataclass
class TrialBase(ABC):
    """
    This is like the Trial concept in BrAPI,
    But using the more widespread terminology from ISA
    https://isa-specs.readthedocs.io/en/latest/isamodel.html
    """
    label: ClassVar[str] = 'Trial'
    plural: ClassVar[str] = 'Trials'

    name: str = None
    fullname: str|None = None
    description: str|None = None

    start: datetime64|None = None
    end: datetime64|None = None

    contacts: List[int] = field(default_factory=list) # list of Person by ID suitable to contact for queries about this study.
    references: List[int] = field(default_factory=list)  # list of reference by ID

    def get_study(self, study_id: int) -> StudyStored | StudyInput | None:
        if isinstance(self, TrialStored):
            return self.studies.get(study_id)
        else:
            raise ValueError("Studies can only be retrieved from stored trials")

    def add_study(self, study: StudyInput):
        if isinstance(self, TrialStored):
            temp_key = -len(self.studies) - 1
            self.studies[temp_key] = study
        else:
            raise ValueError("Studies can only be added to stored trials")

    def remove_study(self, study: StudyStored):
        if isinstance(self, TrialStored):
            self.studies.pop(study.id)
        else:
            raise ValueError("Studies can only be removed from stored trials")

@dataclass
class TrialInput(TrialBase, LabeledModel):
    pass

@dataclass
class TrialStored(TrialBase, ControlledModel):
    studies: Dict[int, StudyStored|StudyInput] = field(default_factory=dict) # keyed by ID or assigned a temporary ID for inputs

    def redacted(
            self,
            controller: Controller,
            user_id=None,
            read_teams=None
    ) -> Self:

        if controller.has_access(Access.READ, user_id, read_teams):
            return self

        return replace(
            self,
            name = self.redacted_str,
            fullname = self.fullname and self.redacted_str,
            description = self.description and self.redacted_str,
            start = None,
            end = None,
            references = list()
        )

@dataclass(eq=False)
class ProgramBase(ABC):
    label: ClassVar[str] = 'Program'
    plural: ClassVar[str] = 'Programs'

    name: str = None
    fullname: str|None = None
    description: str|None = None
    contacts: List[int] = field(default_factory=list) # list of Person by ID suitable to contact for queries about this program.
    references: List[int] = field(default_factory=list)  # list of reference IDs

    def model_dump(self):
        return asdict(self)

    def add_trial(self, trial: TrialInput):
        if isinstance(self, ProgramStored):
            temp_key = -len(self.trials) - 1
            self.trials[temp_key] = trial
        else:
            raise ValueError("Trials can only be added to stored programs")

    def remove_trial(self, trial: TrialStored):
        if isinstance(self, ProgramStored):
            self.trials.pop(trial.id)
        else:
            raise ValueError("Trials can only be removed from stored programs")

    def get_trial(self, trial_id: int):
        if isinstance(self, ProgramStored):
            return self.trials.get(trial_id)
        else:
            raise ValueError("Trials can only be retrieved from stored programs")

    def get_study(self, study_id: int):
        if isinstance(self, ProgramStored):
            for trial in self.trials:
                try:
                    return trial.get_study(study_id)
                except ValueError:
                    pass
            return None
        else:
            raise ValueError("Studies can only be retrieved from stored programs")

    def add_study(self, trial_id: int, study: StudyInput):
        if isinstance(self, ProgramStored):
            trial = self.get_trial(trial_id)
            if trial is not None:
                trial.add_study(study)
            else:
                raise ValueError("Trial not found")
        else:
            raise ValueError("Studies can only be added to stored programs")

    def remove_study(self, study: StudyStored):
        if isinstance(self, ProgramStored):
            for trial in self.trials.values():
                if study.id in trial.studies:
                    trial.remove_study(study)
                    return
            else:
                raise ValueError(f"Study with ID {study.id} not found in any trial for this program")
        else:
            raise ValueError("Studies can only be removed from stored programs")

@dataclass
class ProgramInput(ProgramBase):
    pass

@dataclass(eq=False)
class ProgramStored(ProgramBase, ControlledModel, ControlledAggregate):
    # keyed by ID or assigned a temporary ID for inputs
    trials: Dict[int, TrialStored | TrialInput] = field(default_factory=dict)

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
    ) -> Self:

        program_controller = controllers['Program'][self.id]
        if program_controller.has_access(Access.READ, user_id, read_teams):
            aggregate = self

        else:
            aggregate = replace(
                self,
                name = self.name and self.redacted_str,
                fullname = None,
                description = None,
                contacts = list(),
                references = list()
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
                        aggregate.trials[trial_key].studies.pop(study_key)
                    else:
                        aggregate.trials[trial_key].studies[study_key] = study.redacted(
                            controller=controllers['Study'][study_key],
                            user_id=user_id,
                            read_teams=read_teams
                        )

        return aggregate

    def to_output_map(self):
        return {
            self.id: ProgramOutput(**self.model_dump())
        }


@dataclass(eq=False)
class ProgramOutput(ProgramBase):

    trials: Dict[int, TrialStored | TrialInput] = field(default_factory=dict)


