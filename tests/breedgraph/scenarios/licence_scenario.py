"""
Studies with licences (docs/licences.md), added to a built read-policy scenario (read_policy_scenario.py), for
accepting licences in breedview's curation and analysis (docs/test-databases.md, "The licences"). Fixed names, so
the licences can be asserted.

Everything is controlled by the child team and written by the writer, so the admin and the writer read it through the
team and are not asked to accept the licences, as their owners; the stranger and the outsider are, and anonymous
visitors for the public study.

    Readpolicy licences program                 PUBLIC
    └── Readpolicy licences trial               PUBLIC
        ├── Readpolicy licensed study           PUBLIC      licence: Readpolicy markdown licence, PUBLIC, read from
        │   │                                                licence.md
        │   └── height dataset                  PUBLIC      on tree_public and tree_registered; the tree_public
        │                                                    record cites Readpolicy licensed data, a PUBLIC CSV file
        └── Readpolicy registered licensed study  REGISTERED  licence: Readpolicy PDF licence, REGISTERED, read from
            │                                                  licence.pdf
            ├── height dataset                  REGISTERED  on tree_public
            └── privately cited dataset         PRIVATE     on tree_public; its record cites Readpolicy privately
                                                             cited data, a REGISTERED CSV file, which the study lists
                                                             among its references

Registered users read the privately cited data file, on the study's page, but not the dataset citing it: downloading
the file still needs the PDF licence, which they can read, as a study's licence is released at least as widely as the
files its data cites.
"""
import uuid
from dataclasses import dataclass, field
from typing import Dict, Tuple

from breedgraph.domain.model.controls import ReadRelease
from breedgraph.domain.model.datasets import DatasetInput, DataRecordInput
from breedgraph.domain.model.programs import ProgramInput, TrialInput, StudyInput
from breedgraph.domain.model.references import LegalReferenceInput, FileReferenceInput
from breedgraph.service_layer.infrastructure.legal_files import read_legal_file
from breedgraph.service_layer.infrastructure.unit_of_work import AbstractUnitOfWorkFactory

from tests.breedgraph.utilities.documents import pdf_with_text
from .read_policy_scenario import ReadPolicyScenario, store_file

PROGRAM = "Readpolicy licences program"
TRIAL = "Readpolicy licences trial"
DATA_FILE = "Readpolicy licensed data"
PRIVATELY_CITED_FILE = "Readpolicy privately cited data"

MARKDOWN_LICENCE = b"""# Readpolicy data licence

A licence for the synthetic data of the test database.

1. Use the data **with credit**: cite BreedGraph and the study.
2. Pass the data on only with this licence.

See [the Terms of Use](https://breedgraph.universityofgalway.ie/terms).
"""
PDF_LICENCE = pdf_with_text(
    'Readpolicy registered data licence\nUse the data for research, with credit.',
    'Pass the data on only to registered users, with this licence.'
)

# by key: the study, its release, and its licence's name, file and content
STUDIES: Dict[str, Tuple[str, ReadRelease, str, str, bytes]] = {
    'public': ("Readpolicy licensed study", ReadRelease.PUBLIC, "Readpolicy markdown licence", 'licence.md', MARKDOWN_LICENCE),
    'registered': (
        "Readpolicy registered licensed study", ReadRelease.REGISTERED, "Readpolicy PDF licence", 'licence.pdf', PDF_LICENCE
    ),
}
# by study: the height records, by read-policy unit
HEIGHTS: Dict[str, Dict[str, str]] = {
    'public': {'tree_public': '310', 'tree_registered': '295'},
    'registered': {'tree_public': '305'},
}


@dataclass
class LicenceScenario:
    """The ids of the program, trial, studies, licences, datasets and data file, and the files by name"""
    ids: Dict[str, int] = field(default_factory=dict)
    files: Dict[str, Tuple[str, bytes]] = field(default_factory=dict)  # (file id, content)


class LicenceScenarioBuilder:

    def __init__(self, uow_factory: AbstractUnitOfWorkFactory, base: ReadPolicyScenario, archival_service=None, file_storage_path: str | None = None):
        self.uow_factory = uow_factory
        self.base = base
        self.archival_service = archival_service
        self.file_storage_path = file_storage_path
        self.licences = LicenceScenario()

    def _uow(self, release: ReadRelease):
        """The child team's writer"""
        return self.uow_factory.get_uow(user_id=self.base['writer'], write_team=self.base['child'], release=release)

    async def _store(self, name: str, file_id: str, content: bytes):
        """Write the file of a reference already created with its file id: its archival record is linked to it"""
        self.licences.files[name] = (file_id, content)
        await store_file(self.file_storage_path, self.archival_service, file_id, content)

    async def build(self) -> LicenceScenario:
        ids = self.licences.ids
        async with self._uow(ReadRelease.PUBLIC) as uow:
            program = await uow.repositories.programs.create(ProgramInput(name=PROGRAM))
            program.add_trial(TrialInput(name=TRIAL))
            await uow.repositories.programs.update_seen()
            (trial_id,) = program.trials
            await uow.commit()
        ids.update({'program': program.id, 'trial': trial_id})

        data_file_id = uuid.uuid4().hex
        async with self._uow(ReadRelease.PUBLIC) as uow:
            data_file = await uow.repositories.references.create(FileReferenceInput(
                description=DATA_FILE, filename='licensed_data.csv', content_type='text/csv', file_id=data_file_id
            ))
            await uow.commit()
        await self._store(DATA_FILE, data_file_id, b"unit,height\ntree_public,310\n")
        ids['data_file'] = data_file.id

        for key, (study_name, release, licence_name, filename, content) in STUDIES.items():
            # as referencesCreateLegalFile reads an upload
            legal = read_legal_file(filename, content)
            file_id = uuid.uuid4().hex
            async with self._uow(release) as uow:
                licence = await uow.repositories.references.create(LegalReferenceInput(
                    description=licence_name, text=legal.text, text_format=legal.text_format,
                    content_hash=legal.content_hash, filename=filename, content_type=legal.content_type, file_id=file_id
                ))
                await uow.commit()
            await self._store(licence_name, file_id, content)
            async with self._uow(release) as uow:
                program = await uow.repositories.programs.get(program_id=ids['program'])
                program.add_study(trial_id=trial_id, study=StudyInput(name=study_name, licence_id=licence.id))
                await uow.repositories.programs.update_seen()
                study_id = next(s.id for s in program.get_trial(trial_id).studies.values() if s.name == study_name)
                await uow.commit()
            async with self._uow(release) as uow:
                dataset = await uow.repositories.datasets.create(DatasetInput(
                    concept=self.base['ontology_variable_height'],
                    study=study_id,
                    records=[
                        DataRecordInput(
                            unit_id=self.base[unit], value=value,
                            reference_ids=[data_file.id] if key == 'public' and unit == 'tree_public' else None
                        )
                        for unit, value in HEIGHTS[key].items()
                    ]
                ))
                await uow.commit()
            ids.update({f'{key}_study': study_id, f'{key}_licence': licence.id, f'{key}_dataset': dataset.id})
        await self._privately_cited()
        return self.licences

    async def _privately_cited(self):
        """A registered data file cited only by a private dataset of the registered licensed study"""
        ids = self.licences.ids
        file_id = uuid.uuid4().hex
        async with self._uow(ReadRelease.REGISTERED) as uow:
            data_file = await uow.repositories.references.create(FileReferenceInput(
                description=PRIVATELY_CITED_FILE, filename='privately_cited_data.csv', content_type='text/csv',
                file_id=file_id
            ))
            await uow.commit()
        await self._store(PRIVATELY_CITED_FILE, file_id, b"unit,height\ntree_public,299\n")
        async with self._uow(ReadRelease.PRIVATE) as uow:
            dataset = await uow.repositories.datasets.create(DatasetInput(
                concept=self.base['ontology_variable_height'],
                study=ids['registered_study'],
                records=[DataRecordInput(unit_id=self.base['tree_public'], value='299', reference_ids=[data_file.id])]
            ))
            await uow.commit()
        # listed among the study's references, so that the file shows on its page
        async with self._uow(ReadRelease.REGISTERED) as uow:
            program = await uow.repositories.programs.get(program_id=ids['program'])
            program.get_study(ids['registered_study']).reference_ids.append(data_file.id)
            await uow.commit()
        ids.update({'privately_cited_file': data_file.id, 'privately_cited_dataset': dataset.id})
