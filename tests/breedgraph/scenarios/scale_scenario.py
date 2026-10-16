"""
Data at scale for breedview's performance scripts, added to a built read-policy scenario (read_policy_scenario.py):
generated, not migrated, and built through the repositories as the BreedCAFS migration was, one unit graph per unit of work.

Everything is controlled by the child team and PRIVATE, as the migrated data was, so the admin reads it through their
READ affiliation and the scripts measure the same access checks.

    scale_field_01 .. scale_field_NN       fields (location type Field) below state
    each field: a unit graph rooted at a field unit (subject Field) positioned at the field,
        holding trees (subject Tree), each holding leaves (subject Leaf)
    scale_program > scale_trial > scale_study_01 .. scale_study_NN, one study per field
    scale_study_01: datasets_per_concept datasets of the height variable, each recording every tree of field 01
        at records_per_unit dates
    every other study: one dataset recording every tree of its field once

With the defaults, 20 fields of 1,000 trees with 4 leaves each give 100,020 units; study 01 holds 5 datasets of 5,000
records, 25,000 in all, and the others 1,000 records each.
"""
from dataclasses import dataclass, field

from numpy import datetime64, timedelta64

from breedgraph.domain.model.unit_graphs import UnitInput, Position
from breedgraph.domain.model.controls import ReadRelease
from breedgraph.domain.model.datasets import DatasetInput, DataRecordInput
from breedgraph.domain.model.programs import ProgramInput, TrialInput
from breedgraph.domain.model.location_trees import LocationInput
from breedgraph.service_layer.infrastructure.unit_of_work import AbstractUnitOfWorkFactory

from .program_builder import ProgramBuilder
from .read_policy_scenario import ReadPolicyScenario

import logging
logger = logging.getLogger(__name__)

FIRST_DATE = datetime64('2024-01-15')


@dataclass
class ScaleParameters:
    fields: int = 20
    trees_per_field: int = 1000
    leaves_per_tree: int = 4
    datasets_per_concept: int = 5
    records_per_unit: int = 5


@dataclass
class ScaleScenario:
    """Names and ids of what was built, and its counts, for the manifest"""
    parameters: ScaleParameters
    names: dict[str, str] = field(default_factory=dict)  # key: the name shown in the app
    ids: dict[str, int] = field(default_factory=dict)  # key: id
    dataset_ids: dict[str, list[int]] = field(default_factory=dict)  # study key: its datasets
    unit_count: int = 0
    record_count: int = 0


def field_key(number: int) -> str:
    return f"scale_field_{number:02d}"


def study_key(number: int) -> str:
    return f"scale_study_{number:02d}"


class ScaleScenarioBuilder:

    def __init__(self, uow_factory: AbstractUnitOfWorkFactory, base: ReadPolicyScenario, parameters: ScaleParameters):
        self.uow_factory = uow_factory
        self.base = base
        self.scale = ScaleScenario(parameters=parameters)

    def _uow(self):
        """The child team's writer, PRIVATE, as the migrated data was"""
        return self.uow_factory.get_uow(
            user_id=self.base['writer'], write_team=self.base['child'], release=ReadRelease.PRIVATE
        )

    def _name(self, key: str, name: str):
        self.scale.names[key] = name

    async def build(self) -> ScaleScenario:
        await self._fields()
        tree_ids = {}
        for number in range(1, self.scale.parameters.fields + 1):
            tree_ids[number] = await self._unit_graph(number)
            logger.info(f"Field {number}: {self.scale.unit_count} units so far")
        await self._program()
        for number in range(1, self.scale.parameters.fields + 1):
            await self._datasets(number, tree_ids[number])
            logger.info(f"Study {number}: {self.scale.record_count} records so far")
        return self.scale

    async def _fields(self):
        b = self.base
        names = {field_key(n): f"Readpolicy scale field {n:02d}" for n in range(1, self.scale.parameters.fields + 1)}
        async with self._uow() as uow:
            location_tree = await uow.repositories.location_trees.get(location_id=b['state'])
            for name in names.values():
                location_tree.add_location(LocationInput(name=name, type=b['ontology_location_field']), parent_id=b['state'])
            await uow.commit()
        async with self.uow_factory.get_uow() as uow:
            location_tree = await uow.repositories.location_trees.get(location_id=b['state'])
            by_name = {location.name: location.id for location in location_tree.entries.values()}
        for key, name in names.items():
            self._name(key, name)
            self.scale.ids[key] = by_name[name]

    async def _unit_graph(self, number: int) -> list[int]:
        """The field's unit graph; the ids of its trees, in order"""
        b, p = self.base, self.scale.parameters
        prefix = f"F{number:02d}"
        async with self._uow() as uow:
            unit_graph = await uow.repositories.unit_graphs.create(UnitInput(
                name=f"Readpolicy scale field unit {number:02d}",
                subject=b['ontology_subject_field'],
                positions=[Position(location_id=self.scale.ids[field_key(number)])]
            ))
            root_id = unit_graph.get_root_id()
            for tree in range(1, p.trees_per_field + 1):
                tree_temp = unit_graph.add_unit(
                    UnitInput(name=f"{prefix} T{tree:04d}", subject=b['ontology_subject_tree']), parents=[root_id]
                )
                for leaf in range(1, p.leaves_per_tree + 1):
                    unit_graph.add_unit(
                        UnitInput(name=f"{prefix} T{tree:04d} L{leaf}", subject=b['ontology_subject_leaf']),
                        parents=[tree_temp]
                    )
            await uow.commit()
            root_id = unit_graph.get_root_id()
        self.scale.ids[f"scale_field_unit_{number:02d}"] = root_id
        self.scale.unit_count += 1 + p.trees_per_field * (1 + p.leaves_per_tree)

        async with self.uow_factory.get_uow() as uow:
            unit_graph = await uow.repositories.unit_graphs.get(unit_id=root_id)
            trees = {unit.name: unit.id for unit in unit_graph.entries.values() if unit.subject == b['ontology_subject_tree']}
        return [trees[f"{prefix} T{tree:04d}"] for tree in range(1, p.trees_per_field + 1)]

    async def _program(self):
        b, p = self.base, self.scale.parameters
        async with self._uow() as uow:
            program = await uow.repositories.programs.create(ProgramInput(name="Readpolicy scale program"))
            program.add_trial(TrialInput(name="Readpolicy scale trial"))
            await uow.repositories.programs.update_seen()
            (trial_id,) = program.trials
            for number in range(1, p.fields + 1):
                study = ProgramBuilder.study_input(
                    replicate_type=b['ontology_record_group_replicate'], batch_type=b['ontology_record_group_batch']
                )
                study.name = f"Readpolicy scale study {number:02d}"
                program.add_study(trial_id=trial_id, study=study)
            await uow.repositories.programs.update_seen()
            studies = {study.name: study.id for study in program.get_trial(trial_id).studies.values()}
            await uow.commit()
        for key, name, entity_id in (
                ('scale_program', "Readpolicy scale program", program.id),
                ('scale_trial', "Readpolicy scale trial", trial_id),
        ):
            self._name(key, name)
            self.scale.ids[key] = entity_id
        for number in range(1, p.fields + 1):
            name = f"Readpolicy scale study {number:02d}"
            self._name(study_key(number), name)
            self.scale.ids[study_key(number)] = studies[name]

    async def _datasets(self, number: int, tree_ids: list[int]):
        """The large study records every tree at several dates in several datasets; the others once, in one"""
        b, p = self.base, self.scale.parameters
        large = number == 1
        dataset_count = p.datasets_per_concept if large else 1
        dates = p.records_per_unit if large else 1
        dataset_ids = []
        for dataset in range(dataset_count):
            records = [
                DataRecordInput(
                    unit=tree_id,
                    # a plausible height that grows over the season, varying by tree and dataset
                    value=str(1500 + (index * 37 + dataset * 101) % 800 + date * 25),
                    start=FIRST_DATE + timedelta64(dataset * 7 + date * 30, 'D')
                )
                for index, tree_id in enumerate(tree_ids)
                for date in range(dates)
            ]
            async with self._uow() as uow:
                stored = await uow.repositories.datasets.create(DatasetInput(
                    concept=b['ontology_variable_height'],
                    study=self.scale.ids[study_key(number)],
                    records=records
                ))
                await uow.commit()
            dataset_ids.append(stored.id)
            self.scale.record_count += len(records)
        self.scale.dataset_ids[study_key(number)] = dataset_ids
