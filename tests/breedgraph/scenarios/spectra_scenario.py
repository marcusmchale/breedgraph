"""
Records of a variable on a complex scale, which cite data files rather than hold values, added to a built read-policy
scenario (read_policy_scenario.py), for choosing a record's files in breedview's curation and dataset submission tables
(docs/test-databases.md, "The spectra"). Fixed names, so the files can be searched for and asserted.

The variable is the read-policy ontology's canopy spectrum, built before that scenario's last commit: a commit activates
every draft, and ontology_subject_draft must stay one. Everything here is controlled by the child team, PRIVATE, and
written by the writer, who curates it: only the admin and the writer read it, so what other viewers see is unchanged.

    Readpolicy spectra program                    PRIVATE
    └── Readpolicy spectra trial                  PRIVATE
        ├── Readpolicy spectra study              PRIVATE
        │   └── canopy spectrum dataset           PRIVATE     a record on tree_public citing Readpolicy canopy spectrum
        │                                                      1, and one on tree_registered citing Readpolicy canopy
        │                                                      spectrum 2, both read on 2025-06-12
        └── Readpolicy spectra submission study   PRIVATE     no datasets: for breedview's tests to submit to

    Readpolicy canopy spectrum 1 and 2            PRIVATE     data files (CSV) of reflectance by wavelength
"""
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from numpy import datetime64

from breedgraph.domain.model.controls import ReadRelease
from breedgraph.domain.model.datasets import DatasetInput, DataRecordInput
from breedgraph.domain.model.programs import ProgramInput, TrialInput, StudyInput
from breedgraph.domain.model.references import DataFileInput, DataFormat
from breedgraph.service_layer.infrastructure.unit_of_work import AbstractUnitOfWorkFactory

from .read_policy_scenario import ReadPolicyScenario, store_file

PROGRAM = "Readpolicy spectra program"
TRIAL = "Readpolicy spectra trial"
STUDY = "Readpolicy spectra study"
SUBMISSION_STUDY = "Readpolicy spectra submission study"
READ_ON = '2025-06-12'

# The data files by name (their description): (filename, content)
FILES: Dict[str, Tuple[str, bytes]] = {
    "Readpolicy canopy spectrum 1": (
        'canopy_spectrum_1.csv', b"wavelength_nm,reflectance\n450,0.041\n550,0.112\n680,0.036\n800,0.487\n"
    ),
    "Readpolicy canopy spectrum 2": (
        'canopy_spectrum_2.csv', b"wavelength_nm,reflectance\n450,0.038\n550,0.104\n680,0.033\n800,0.512\n"
    ),
}
# The records by read-policy unit: the files each cites
RECORDS: Dict[str, List[str]] = {
    'tree_public': ["Readpolicy canopy spectrum 1"],
    'tree_registered': ["Readpolicy canopy spectrum 2"],
}


@dataclass
class SpectraScenario:
    """
    The ids of the program, trial, studies and dataset; the files' reference ids and their file ids and contents, by
    name; and the record ids by unit
    """
    ids: Dict[str, int] = field(default_factory=dict)
    references: Dict[str, int] = field(default_factory=dict)
    files: Dict[str, Tuple[str, bytes]] = field(default_factory=dict)  # (file id, content)
    records: Dict[str, int] = field(default_factory=dict)


class SpectraScenarioBuilder:

    def __init__(self, uow_factory: AbstractUnitOfWorkFactory, base: ReadPolicyScenario, archival_service=None, file_storage_path: str | None = None):
        self.uow_factory = uow_factory
        self.base = base
        self.archival_service = archival_service
        self.file_storage_path = file_storage_path
        self.spectra = SpectraScenario()

    def _uow(self):
        """The child team's writer, writing PRIVATE"""
        return self.uow_factory.get_uow(user_id=self.base['writer'], write_team=self.base['child'], release=ReadRelease.PRIVATE)

    async def build(self) -> SpectraScenario:
        ids = self.spectra.ids
        async with self._uow() as uow:
            program = await uow.repositories.programs.create(ProgramInput(name=PROGRAM))
            program.add_trial(TrialInput(name=TRIAL))
            await uow.repositories.programs.update_seen()
            (trial_id,) = program.trials
            await uow.commit()
        ids.update({'program': program.id, 'trial': trial_id})

        async with self._uow() as uow:
            program = await uow.repositories.programs.get(program_id=ids['program'])
            for name in (STUDY, SUBMISSION_STUDY):
                program.add_study(trial_id=trial_id, study=StudyInput(name=name))
            await uow.repositories.programs.update_seen()
            studies = {study.name: study.id for study in program.get_trial(trial_id).studies.values()}
            await uow.commit()
        ids.update({'study': studies[STUDY], 'submission_study': studies[SUBMISSION_STUDY]})

        for name, (filename, content) in FILES.items():
            file_id = uuid.uuid4().hex
            async with self._uow() as uow:
                reference = await uow.repositories.references.create(DataFileInput(
                    description=name, filename=filename, content_type='text/csv', file_id=file_id, format=DataFormat.CSV
                ))
                await uow.commit()
            self.spectra.references[name] = reference.id
            self.spectra.files[name] = (file_id, content)
            await store_file(self.file_storage_path, self.archival_service, file_id, content)

        # no values: a record on a complex scale cites the files of its readings instead
        async with self._uow() as uow:
            dataset = await uow.repositories.datasets.create(DatasetInput(
                concept=self.base['ontology_variable_spectrum'],
                study=ids['study'],
                records=[
                    DataRecordInput(
                        unit_id=self.base[unit], start=datetime64(READ_ON),
                        reference_ids=[self.spectra.references[name] for name in names]
                    )
                    for unit, names in RECORDS.items()
                ]
            ))
            await uow.commit()
        ids['dataset'] = dataset.id
        units = {self.base[unit]: unit for unit in RECORDS}
        self.spectra.records = {units[record.unit]: record.id for record in dataset.records}
        return self.spectra
