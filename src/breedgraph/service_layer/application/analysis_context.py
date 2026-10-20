"""
Loads the data required to prepare an analysis, within a unit of work scoped to the requesting user.
"""
from breedgraph.domain.model.analysis import (
    AnalysisRequest, AnalysisMessage, AnalysisErrorCode, AnalysisWarningCode, AnalysisFailed, AnalysisTermType
)
from breedgraph.domain.model.analysis_context import AnalysisContext, ConceptContext, UnitContext
from breedgraph.domain.model.controls import ControlledModelLabel, Access
from breedgraph.domain.model.datasets import DatasetStored
from breedgraph.domain.model.ontology import OntologyEntryLabel, ScaleType, ScaleCategoryStored, FactorStored
from breedgraph.domain.model.programs import StudyStored
from breedgraph.service_layer.infrastructure.unit_of_work import AbstractUnitHolder

import logging
logger = logging.getLogger(__name__)


class AnalysisContextLoader:

    def __init__(self, uow: AbstractUnitHolder, user_id: int, warnings: list[AnalysisMessage]):
        """
        :param warnings: list to which warnings are appended
        """
        self.uow = uow
        self.user_id = user_id
        self.warnings = warnings
        self.errors: list[AnalysisMessage] = []

    def _raise_errors(self):
        if self.errors:
            raise AnalysisFailed(self.errors)

    async def load(self, request: AnalysisRequest) -> AnalysisContext:
        spec_path = [request.analysis_type.input_field]
        datasets = await self._load_datasets(request)
        concepts = await self._load_concepts(request, datasets, spec_path)
        self._raise_errors()

        studies = await self._load_studies({dataset.study for dataset in datasets.values()})
        units = await self._load_units(request, datasets, concepts, spec_path)
        germplasm_descendants = await self._load_germplasm(request, spec_path)
        await self._check_subjects(request, spec_path)
        self._raise_errors()

        return AnalysisContext(
            request=request,
            datasets=datasets,
            concepts=concepts,
            units=units,
            studies=studies,
            germplasm_descendants=germplasm_descendants
        )

    async def _load_datasets(self, request: AnalysisRequest) -> dict[int, DatasetStored]:
        datasets = {
            dataset.id: dataset
            async for dataset in self.uow.repositories.datasets.get_all(dataset_ids=request.dataset_ids)
        }
        controllers = await self.uow.controls.get_controllers(
            label=ControlledModelLabel.DATASET, model_ids=list(datasets.keys())
        )
        read_teams = self.uow.controls.access_teams[Access.READ]
        for i, dataset_id in enumerate(request.dataset_ids):
            path = ['datasetIds', str(i)]
            dataset = datasets.get(dataset_id)
            if dataset is None:
                self.errors.append(AnalysisMessage(
                    code=AnalysisErrorCode.DATASET_NOT_FOUND, message=f"Dataset {dataset_id} was not found", path=path
                ))
                continue
            controller = controllers.get(dataset_id)
            if controller is not None and not controller.has_access(Access.READ, self.user_id, read_teams):
                self.errors.append(AnalysisMessage(
                    code=AnalysisErrorCode.DATASET_NOT_READABLE,
                    message=f"Dataset {dataset_id} is not readable",
                    path=path
                ))
                # The repository returns whole datasets, so nothing of an unreadable one may be used
                datasets.pop(dataset_id)
                continue
            if not dataset.records:
                self.warnings.append(AnalysisMessage(
                    code=AnalysisWarningCode.EMPTY_DATASET, message=f"Dataset {dataset_id} has no records", path=path
                ))
        return datasets

    async def _load_concepts(
            self,
            request: AnalysisRequest,
            datasets: dict[int, DatasetStored],
            spec_path: list[str]
    ) -> dict[int, ConceptContext]:
        dataset_concepts = {dataset.concept for dataset in datasets.values()}
        concept_ids = set()
        for i, term in enumerate(request.spec.terms):
            if term.reference.type != AnalysisTermType.CONCEPT:
                continue
            concept_id = term.reference.concept_id
            concept_ids.add(concept_id)
            if concept_id not in dataset_concepts:
                self.errors.append(AnalysisMessage(
                    code=AnalysisErrorCode.CONCEPT_NOT_IN_DATASETS,
                    message=f"Concept {concept_id} is not the concept of any selected dataset",
                    path=spec_path + ['terms', str(i), 'reference', 'conceptId']
                ))

        for i, dataset_id in enumerate(request.dataset_ids):
            dataset = datasets.get(dataset_id)
            if dataset is not None and dataset.concept not in concept_ids:
                self.warnings.append(AnalysisMessage(
                    code=AnalysisWarningCode.UNUSED_DATASET,
                    message=f"The concept of dataset {dataset_id} is not used by any term, its records are ignored",
                    path=['datasetIds', str(i)]
                ))

        concepts = {}
        for concept_id in concept_ids & dataset_concepts:
            concepts[concept_id] = await self._load_concept(concept_id)
        return concepts

    async def _load_concept(self, concept_id: int) -> ConceptContext:
        ontology = self.uow.ontology
        scale_id = await ontology.get_scale_id(entry_id=concept_id)
        scale = await ontology.get_entry(scale_id, label=OntologyEntryLabel.SCALE)
        categories = None
        if scale.scale_type in (ScaleType.ORDINAL, ScaleType.NOMINAL):
            # ordered by rank
            categories = []
            for category_id in await ontology.get_scale_category_ids(scale.id):
                category = await ontology.get_entry(category_id)
                if isinstance(category, ScaleCategoryStored):
                    categories.append(category.name)
        factor = isinstance(await ontology.get_entry(concept_id), FactorStored)
        return ConceptContext(concept_id=concept_id, scale_type=scale.scale_type, categories=categories, factor=factor)

    async def _load_studies(self, study_ids: set[int]) -> dict[int, StudyStored]:
        studies = {}
        for study_id in study_ids:
            program = await self.uow.repositories.programs.get(study_id=study_id)
            if program is not None:
                program = await self.uow.repositories.programs.redacted(program)
            study = program.get_study(study_id=study_id) if program is not None else None
            if study is not None:
                studies[study_id] = study
        return studies

    async def _load_units(
            self,
            request: AnalysisRequest,
            datasets: dict[int, DatasetStored],
            concepts: dict[int, ConceptContext],
            spec_path: list[str]
    ) -> dict[int, UnitContext]:
        unit_ids = {
            record.unit
            for dataset in datasets.values() if dataset.concept in concepts
            for record in dataset.records if record.unit is not None
        }
        selected = request.spec.grouping.unit.unit_ids if request.spec.grouping.unit else []
        unit_ids |= set(selected)

        recorded = unit_ids - set(selected)
        units = {}
        if unit_ids:
            async for unit_graph in self.uow.repositories.unit_graphs.get_all(unit_ids=list(unit_ids)):
                # Units the user cannot read are left out, and ancestors are those the user can read
                redacted = await self.uow.repositories.unit_graphs.redacted(unit_graph)
                for unit_id, unit in redacted.entries.items():
                    units[unit_id] = UnitContext(
                        unit_id=unit_id,
                        subject_id=unit.subject,
                        germplasm_id=unit.germplasm,
                        positions=list(unit.positions or []),
                        ancestor_ids=redacted.get_ancestors(unit_id),
                        # Redaction keeps a hidden root as a placeholder, so this is the root whatever the user reads
                        root_id=redacted.get_root_id()
                    )
                # A readable dataset's records are readable, their hidden units placeholders (docs/read-access.md):
                # such a unit hangs from the nearest units above it that the user can read, without its subject,
                # germplasm or positions, as datasetsUnits shows it
                for unit_id in recorded & set(unit_graph.entries) - set(redacted.entries):
                    units[unit_id] = UnitContext(
                        unit_id=unit_id,
                        ancestor_ids=[a for a in unit_graph.get_ancestors(unit_id) if a in redacted.entries],
                        root_id=redacted.get_root_id()
                    )

        for i, unit_id in enumerate(selected):
            if unit_id not in units:
                self.errors.append(AnalysisMessage(
                    code=AnalysisErrorCode.UNIT_NOT_FOUND,
                    message=f"Unit {unit_id} was not found",
                    path=spec_path + ['grouping', 'unit', 'unitIds', str(i)]
                ))
        return units

    async def _load_germplasm(self, request: AnalysisRequest, spec_path: list[str]) -> dict[int, set[int]]:
        grouping = request.spec.grouping.germplasm
        if grouping is None:
            return {}
        descendants = {}
        for i, germplasm_id in enumerate(grouping.germplasm_ids):
            # the readable entries below it, found through hidden ones; a hidden entry is not found, unless a crop
            descendant_ids = await self.uow.germplasm.get_readable_descendant_ids(germplasm_id)
            if descendant_ids is None:
                self.errors.append(AnalysisMessage(
                    code=AnalysisErrorCode.CONFIG_INVALID,
                    message=f"Germplasm {germplasm_id} was not found",
                    path=spec_path + ['grouping', 'germplasm', 'germplasmIds', str(i)]
                ))
                continue
            descendants[germplasm_id] = set(descendant_ids)
        return descendants

    async def _check_subjects(self, request: AnalysisRequest, spec_path: list[str]):
        """The subjects whose units are levels of record group dimensions must be subjects of the ontology"""
        for i, dimension in enumerate(request.spec.grouping.record_groups):
            for j, subject_id in enumerate(dimension.subject_ids):
                if await self.uow.ontology.get_entry(subject_id, label=OntologyEntryLabel.SUBJECT) is None:
                    self.errors.append(AnalysisMessage(
                        code=AnalysisErrorCode.CONFIG_INVALID,
                        message=f"Subject {subject_id} was not found",
                        path=spec_path + ['grouping', 'recordGroups', str(i), 'subjectIds', str(j)]
                    ))
