"""
Loads the data required to prepare an analysis, within a unit of work scoped to the requesting user.
"""
from breedgraph.domain.model.analysis import (
    AnalysisRequest, AnalysisMessage, AnalysisErrorCode, AnalysisWarningCode, AnalysisFailed, AnalysisTermType
)
from breedgraph.domain.model.analysis_context import (
    AnalysisContext, ConceptContext, UnitContext, LocationContext, LayoutContext
)
from breedgraph.domain.model.controls import ControlledModelLabel, Access
from breedgraph.domain.model.datasets import DatasetStored
from breedgraph.domain.model.ontology import OntologyEntryLabel
from breedgraph.domain.model.programs import StudyStored
from breedgraph.domain.model.unit_graphs import UnitGraph
from breedgraph.domain.services.lineages import lineage_value, nearest_on_each_lineage, germplasm_seen, HIDDEN
from breedgraph.service_layer.infrastructure.unit_of_work import AbstractUnitHolder

import logging
logger = logging.getLogger(__name__)

def _nearest_seen(unit_graph: UnitGraph, unit_id: int, seen: set[int]) -> list[int]:
    """The nearest units above a hidden unit that the user can read, one on each lineage"""
    return nearest_on_each_lineage(unit_id, unit_graph.get_parent_ids, lambda u: u in seen)


def _hidden_positioned(unit_graph: UnitGraph, redacted: UnitGraph) -> set[int]:
    """The units with positions the user cannot see: hidden ones, which stop a placement (docs/read-access.md, rule 3)"""
    return {
        unit_id for unit_id, unit in unit_graph.entries.items()
        if unit.positions and not (redacted.has_unit(unit_id) and redacted.get_unit(unit_id).positions)
    }


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
        hidden_positioned: set[int] = set()
        units = await self._load_units(request, datasets, concepts, spec_path, hidden_positioned)
        germplasm_descendants = await self._load_germplasm(request, spec_path)
        await self._check_subjects(request, spec_path)
        await self._check_position_grouping(request, spec_path)
        self._raise_errors()
        locations, layouts = await self._load_places(request, units)

        return AnalysisContext(
            request=request,
            datasets=datasets,
            concepts=concepts,
            units=units,
            studies=studies,
            germplasm_descendants=germplasm_descendants,
            locations=locations,
            layouts=layouts,
            hidden_positioned=hidden_positioned
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
        # as the data cites it, so that data of a removed variable or factor is still analysed
        ontology = self.uow.ontology
        scale, categories = await ontology.get_concept_scale(concept_id)
        concept = await ontology.get_cited_entry(concept_id)
        return ConceptContext(
            concept_id=concept_id,
            scale_type=scale.scale_type,
            # ordered by rank
            categories=[category.name for category in categories] if categories is not None else None,
            factor=concept.label is OntologyEntryLabel.FACTOR
        )

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
            spec_path: list[str],
            hidden_positioned: set[int]
    ) -> dict[int, UnitContext]:
        """
        :param hidden_positioned: set to which the hidden units with positions are added, for position grouping
        """
        unit_ids = {
            record.unit
            for dataset in datasets.values() if dataset.concept in concepts
            for record in dataset.records if record.unit is not None
        }
        selected = request.spec.grouping.unit.unit_ids if request.spec.grouping.unit else []
        unit_ids |= set(selected)

        recorded = unit_ids - set(selected)
        placing = request.spec.grouping.position is not None
        units = {}
        if unit_ids:
            async for unit_graph in self.uow.repositories.unit_graphs.get_all(unit_ids=list(unit_ids)):
                # Units the user cannot read are left out, and ancestors are those the user can read
                redacted = await self.uow.repositories.unit_graphs.redacted(unit_graph)
                germplasm_of = germplasm_seen(unit_graph, redacted)
                if placing:
                    hidden = _hidden_positioned(unit_graph, redacted)
                    hidden_positioned |= hidden
                    # a placement passes through hidden units without positions and stops at those with them
                    shown = set(redacted.entries) | hidden
                for unit_id, unit in redacted.entries.items():
                    # its own germplasm or the one its lineages agree on, walked on the whole graph: a hidden unit
                    # with germplasm is where a lineage stops, unknown, so the unit takes none
                    germplasm, _ = lineage_value(unit_id, unit_graph.get_parent_ids, germplasm_of)
                    units[unit_id] = UnitContext(
                        unit_id=unit_id,
                        subject_id=unit.subject,
                        germplasm_id=None if germplasm is HIDDEN else germplasm,
                        positions=list(unit.positions or []),
                        ancestor_ids=redacted.get_ancestors(unit_id),
                        parent_ids=redacted.get_parent_ids(unit_id),
                        # Redaction keeps a hidden root as a placeholder, so this is the root whatever the user reads
                        root_id=redacted.get_root_id(),
                        place_parent_ids=nearest_on_each_lineage(
                            unit_id, unit_graph.get_parent_ids, lambda u: u in shown
                        ) if placing else []
                    )
                # A readable dataset's records are readable, their hidden units placeholders (docs/read-access.md):
                # such a unit hangs from the nearest units above it that the user can read, without its subject,
                # germplasm or positions, as datasetsUnits shows it
                for unit_id in recorded & set(unit_graph.entries) - set(redacted.entries):
                    ancestor_ids = [a for a in unit_graph.get_ancestors(unit_id) if a in redacted.entries]
                    units[unit_id] = UnitContext(
                        unit_id=unit_id,
                        ancestor_ids=ancestor_ids,
                        parent_ids=_nearest_seen(unit_graph, unit_id, set(redacted.entries)),
                        root_id=redacted.get_root_id(),
                        readable=False
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

    async def _check_position_grouping(self, request: AnalysisRequest, spec_path: list[str]):
        """The location types and subjects of position grouping must be in the ontology"""
        grouping = request.spec.grouping.position
        if grouping is None:
            return
        path = spec_path + ['grouping', 'position']
        for i, type_id in enumerate(grouping.location_type_ids):
            if await self.uow.ontology.get_cited_entry(type_id, label=OntologyEntryLabel.LOCATION_TYPE) is None:
                self.errors.append(AnalysisMessage(
                    code=AnalysisErrorCode.CONFIG_INVALID,
                    message=f"Location type {type_id} was not found",
                    path=path + ['locationTypeIds', str(i)]
                ))
        for i, subject_id in enumerate(grouping.subject_ids):
            if await self.uow.ontology.get_cited_entry(subject_id, label=OntologyEntryLabel.SUBJECT) is None:
                self.errors.append(AnalysisMessage(
                    code=AnalysisErrorCode.CONFIG_INVALID,
                    message=f"Subject {subject_id} was not found",
                    path=path + ['subjectIds', str(i)]
                ))

    async def _load_places(
            self,
            request: AnalysisRequest,
            units: dict[int, UnitContext]
    ) -> tuple[dict[int, LocationContext], dict[int, LayoutContext]]:
        """
        For position grouping, the location trees and layout trees of the units' positions as the user sees them:
        hidden members skipped, a hidden root kept as a placeholder (docs/read-access.md, rules 3 and 4)
        """
        grouping = request.spec.grouping.position
        if grouping is None:
            return {}, {}
        positions = [position for unit in units.values() for position in unit.positions]
        read_teams = self.uow.controls.access_teams[Access.READ]

        locations: dict[int, LocationContext] = {}
        loaded: set[int] = set()  # every location of the trees read, hidden ones too
        for location_id in sorted({position.location_id for position in positions}):
            if location_id in loaded:
                continue
            tree = await self.uow.repositories.location_trees.get(location_id=location_id)
            if tree is None:
                continue
            loaded |= set(tree.entries)
            redacted = await self.uow.repositories.location_trees.redacted(tree)
            controllers = await self.uow.controls.get_controllers(ControlledModelLabel.LOCATION, list(redacted.entries))
            for node_id, location in redacted.entries.items():
                controller = controllers.get(node_id)
                readable = controller is not None and controller.has_access(Access.READ, self.user_id, read_teams)
                locations[node_id] = LocationContext(
                    location_id=node_id,
                    type_id=location.type if readable else None,
                    parent_id=redacted.get_parent_id(node_id),
                    readable=readable
                )

        layouts: dict[int, LayoutContext] = {}
        if not grouping.axes:
            return locations, layouts
        loaded = set()
        for layout_id in sorted({position.layout_id for position in positions if position.layout_id is not None}):
            if layout_id in loaded:
                continue
            tree = await self.uow.repositories.layout_trees.get(layout_id=layout_id)
            if tree is None:
                continue
            loaded |= set(tree.entries)
            redacted = await self.uow.repositories.layout_trees.redacted(tree)
            controllers = await self.uow.controls.get_controllers(ControlledModelLabel.LAYOUT, list(redacted.entries))
            for node_id, layout in redacted.entries.items():
                controller = controllers.get(node_id)
                readable = controller is not None and controller.has_access(Access.READ, self.user_id, read_teams)
                layouts[node_id] = LayoutContext(
                    layout_id=node_id,
                    axes=list(layout.axes or []) if readable else [],
                    parent_id=redacted.get_parent_id(node_id),
                    # where a hidden layout was skipped, the joined edge has no position
                    position=redacted.get_position(node_id),
                    readable=readable
                )
        return locations, layouts

    async def _check_subjects(self, request: AnalysisRequest, spec_path: list[str]):
        """The subjects whose units are levels of record group dimensions must be subjects of the ontology"""
        for i, dimension in enumerate(request.spec.grouping.record_groups):
            for j, subject_id in enumerate(dimension.subject_ids):
                if await self.uow.ontology.get_cited_entry(subject_id, label=OntologyEntryLabel.SUBJECT) is None:
                    self.errors.append(AnalysisMessage(
                        code=AnalysisErrorCode.CONFIG_INVALID,
                        message=f"Subject {subject_id} was not found",
                        path=spec_path + ['grouping', 'recordGroups', str(i), 'subjectIds', str(j)]
                    ))
