"""
A study whose records carry record group codes of every extent and scope, added to a built read-policy scenario
(read_policy_scenario.py), for breedview's record group and replicate aggregation checks. Generated, with fixed names
and exact values, so labels and means can be asserted.

Everything is controlled by the child team and REGISTERED: the admin reads it (READ on child), the writer reads and
curates it, and every account reads it as a registered user.

    Rep Field A, Rep Field B          unit graphs: a field unit (subject Field) positioned at field_registered,
                                      with two plots (subject Plot), each with three trees (subject Tree):
                                      Rep A1-A3 in Rep Plot A1, Rep A4-A6 in Rep Plot A2, and so for B
    Readpolicy replicates program > trial > study, with the groupings:

    grouping                              type                  extent        scope
    Dataset Scoped Replicate              Replicate             WITHIN_UNIT   DATASET_SCOPED, same_time with width
    Study Scoped Biological Replicate     Biological Replicate  WITHIN_UNIT   STUDY_WIDE
    Study Scoped Batch                    Batch                 SHARED        STUDY_WIDE
    Dataset Scoped Plate                  Plate                 SHARED        DATASET_SCOPED, same_time with width
    Study Scoped Block                    Block                 WITHIN_GRAPH  STUDY_WIDE
    Dataset Scoped Block                  Block                 WITHIN_GRAPH  DATASET_SCOPED

Datasets (DATASETS below gives each record): every record carries its unit's Study Scoped Block code, "Block 1" for
the first plot of a field and "Block 2" for the second, so the same codes name a different level in each field.

    same_time      height  replicates 1-3 of each tree at one start, but only 1-2 of Rep A6 (unequal counts);
                           Plate A for plot 1 and B for plot 2
    width          width   the same trees, starts, replicate and plate codes as same_time
    windowed       height  replicates 1-3 of each tree at 10:00, 10:03 and 10:20 on one date
    dated          height  replicates 1-3 of each tree on three dates
    biorep         height  biological replicates 1-2 of each tree at one start
    biorep_width   width   the same trees, start and biological replicate codes as biorep
    factor         light   one undated record per plot
    blocks         height  each tree once, with Batch 1 for odd and Batch 2 for even trees, across fields
    regrouped      height  each tree once, with Dataset Scoped Block "Block A" for a plot's first two trees and
                           "Block B" for its third
"""
from dataclasses import dataclass, field

from numpy import datetime64

from breedgraph.domain.model.controls import ReadRelease
from breedgraph.domain.model.datasets import DatasetInput, DataRecordInput, RecordGroup
from breedgraph.domain.model.ontology import RecordGroupExtent
from breedgraph.domain.model.programs import (
    ProgramInput, TrialInput, StudyInput, RecordGroupingInput, GroupingScope
)
from breedgraph.domain.model.unit_graphs import UnitInput, Position
from breedgraph.service_layer.infrastructure.unit_of_work import AbstractUnitOfWorkFactory

from .read_policy_scenario import ReadPolicyScenario

PROGRAM = "Readpolicy replicates program"
TRIAL = "Readpolicy replicates trial"
STUDY = "Readpolicy replicates study"

FIELDS = ('A', 'B')
PLOTS_PER_FIELD = 2
TREES_PER_PLOT = 3

REPLICATE = "Dataset Scoped Replicate"
BIOREP = "Study Scoped Biological Replicate"
BATCH = "Study Scoped Batch"
PLATE = "Dataset Scoped Plate"
BLOCK = "Study Scoped Block"
DATASET_BLOCK = "Dataset Scoped Block"

# grouping: (type key, extent, scope)
GROUPINGS = {
    REPLICATE: ('ontology_record_group_replicate', RecordGroupExtent.WITHIN_UNIT, GroupingScope.DATASET_SCOPED),
    BIOREP: ('ontology_record_group_biorep', RecordGroupExtent.WITHIN_UNIT, GroupingScope.STUDY_WIDE),
    BATCH: ('ontology_record_group_batch', RecordGroupExtent.SHARED, GroupingScope.STUDY_WIDE),
    PLATE: ('ontology_record_group_plate', RecordGroupExtent.SHARED, GroupingScope.DATASET_SCOPED),
    BLOCK: ('ontology_record_group_block', RecordGroupExtent.WITHIN_GRAPH, GroupingScope.STUDY_WIDE),
    DATASET_BLOCK: ('ontology_record_group_block', RecordGroupExtent.WITHIN_GRAPH, GroupingScope.DATASET_SCOPED),
}

# dataset-scoped groupings: the datasets whose codes are comparable, beyond each dataset alone
DATASET_SCOPES = {
    REPLICATE: [('same_time', 'width')],
    PLATE: [('same_time', 'width')],
}


def field_name(f: str) -> str:
    return f"Rep Field {f}"


def plot_name(f: str, plot: int) -> str:
    return f"Rep Plot {f}{plot}"


def tree_name(f: str, tree: int) -> str:
    return f"Rep {f}{tree}"


def plot_of(tree: int) -> int:
    """The plot (1-based) of a tree, numbered 1-based across its field"""
    return (tree - 1) // TREES_PER_PLOT + 1


TREES = [(f, tree) for f in FIELDS for tree in range(1, PLOTS_PER_FIELD * TREES_PER_PLOT + 1)]
PLOTS = [(f, plot) for f in FIELDS for plot in range(1, PLOTS_PER_FIELD + 1)]


@dataclass(frozen=True)
class Record:
    """A record of the scenario, by unit name and grouping name, resolved to ids when built"""
    unit: str
    value: str
    start: str | None = None
    groups: tuple[tuple[str, str], ...] = ()


def _block(tree: int) -> tuple[str, str]:
    return BLOCK, f"Block {plot_of(tree)}"


def _same_time(value) -> list[Record]:
    """Replicates 1-3 of every tree at one start, 1-2 of Rep A6; plates by plot"""
    records = []
    for index, (f, tree) in enumerate(TREES):
        codes = (1, 2) if (f, tree) == ('A', 6) else (1, 2, 3)
        for code in codes:
            records.append(Record(
                unit=tree_name(f, tree),
                value=str(value(index, code)),
                start='2024-06-03',
                groups=(
                    (REPLICATE, str(code)),
                    (PLATE, 'A' if plot_of(tree) == 1 else 'B'),
                    _block(tree)
                )
            ))
    return records


def _windowed() -> list[Record]:
    return [
        Record(
            unit=tree_name(f, tree),
            value=str(1200 + 100 * index + 10 * code),
            start=f'2024-06-10T{time}',
            groups=((REPLICATE, str(code)), _block(tree))
        )
        for index, (f, tree) in enumerate(TREES)
        for code, time in ((1, '10:00'), (2, '10:03'), (3, '10:20'))
    ]


def _dated() -> list[Record]:
    return [
        Record(
            unit=tree_name(f, tree),
            value=str(1300 + 100 * index + 20 * code),
            start=date,
            groups=((REPLICATE, str(code)), _block(tree))
        )
        for index, (f, tree) in enumerate(TREES)
        for code, date in ((1, '2024-07-01'), (2, '2024-07-08'), (3, '2024-07-15'))
    ]


def _biorep(value) -> list[Record]:
    return [
        Record(
            unit=tree_name(f, tree),
            value=str(value(index, code)),
            start='2024-06-17',
            groups=((BIOREP, str(code)), _block(tree))
        )
        for index, (f, tree) in enumerate(TREES)
        for code in (1, 2)
    ]


def _factor() -> list[Record]:
    return [
        Record(unit=plot_name(f, plot), value=str(200 + 50 * index), groups=((BLOCK, f"Block {plot}"),))
        for index, (f, plot) in enumerate(PLOTS)
    ]


def _blocks() -> list[Record]:
    return [
        Record(
            unit=tree_name(f, tree),
            value=str(1400 + 100 * index),
            start='2024-08-05',
            groups=(_block(tree), (BATCH, f"Batch {2 - tree % 2}"))
        )
        for index, (f, tree) in enumerate(TREES)
    ]


def _regrouped() -> list[Record]:
    return [
        Record(
            unit=tree_name(f, tree),
            value=str(1500 + 100 * index),
            start='2024-08-12',
            groups=(_block(tree), (DATASET_BLOCK, "Block B" if tree % TREES_PER_PLOT == 0 else "Block A"))
        )
        for index, (f, tree) in enumerate(TREES)
    ]


# dataset key: (concept key, records). Rep A6's same_time replicates are high, so its mean pulls the pooled mean
# of plot A2 away from the mean of the tree means there.
DATASETS: dict[str, tuple[str, list[Record]]] = {
    'same_time': ('ontology_variable_height', _same_time(lambda index, code: 1000 + 100 * index + 10 * code + (600 if index == 5 else 0))),
    'width': ('ontology_variable_width', _same_time(lambda index, code: 2000 + 50 * index + 5 * code)),
    'windowed': ('ontology_variable_height', _windowed()),
    'dated': ('ontology_variable_height', _dated()),
    'biorep': ('ontology_variable_height', _biorep(lambda index, code: 1100 + 100 * index + 30 * code)),
    'biorep_width': ('ontology_variable_width', _biorep(lambda index, code: 2100 + 50 * index + 15 * code)),
    'factor': ('ontology_factor_light', _factor()),
    'blocks': ('ontology_variable_height', _blocks()),
    'regrouped': ('ontology_variable_height', _regrouped()),
}


@dataclass
class ReplicateScenario:
    """Ids of what was built, for the manifest"""
    ids: dict[str, int] = field(default_factory=dict)  # program, trial, study
    units: dict[str, int] = field(default_factory=dict)  # unit name: id
    groupings: dict[str, int] = field(default_factory=dict)  # grouping name: id
    datasets: dict[str, int] = field(default_factory=dict)  # dataset key: id


class ReplicateScenarioBuilder:

    def __init__(self, uow_factory: AbstractUnitOfWorkFactory, base: ReadPolicyScenario):
        self.uow_factory = uow_factory
        self.base = base
        self.replicates = ReplicateScenario()

    def _uow(self):
        """The child team's writer, REGISTERED"""
        return self.uow_factory.get_uow(
            user_id=self.base['writer'], write_team=self.base['child'], release=ReadRelease.REGISTERED
        )

    async def build(self) -> ReplicateScenario:
        for f in FIELDS:
            await self._unit_graph(f)
        await self._program()
        for key in DATASETS:
            await self._dataset(key)
        await self._dataset_scopes()
        return self.replicates

    async def _unit_graph(self, f: str):
        b = self.base
        async with self._uow() as uow:
            unit_graph = await uow.repositories.unit_graphs.create(UnitInput(
                name=field_name(f),
                subject=b['ontology_subject_field'],
                positions=[Position(location_id=b['field_registered'])]
            ))
            root_id = unit_graph.get_root_id()
            for plot in range(1, PLOTS_PER_FIELD + 1):
                plot_temp = unit_graph.add_unit(
                    UnitInput(name=plot_name(f, plot), subject=b['ontology_subject_plot']), parents=[root_id]
                )
                for tree in range((plot - 1) * TREES_PER_PLOT + 1, plot * TREES_PER_PLOT + 1):
                    unit_graph.add_unit(
                        UnitInput(name=tree_name(f, tree), subject=b['ontology_subject_tree']), parents=[plot_temp]
                    )
            await uow.commit()
            root_id = unit_graph.get_root_id()
        async with self.uow_factory.get_uow() as uow:
            unit_graph = await uow.repositories.unit_graphs.get(unit_id=root_id)
            self.replicates.units.update({unit.name: unit.id for unit in unit_graph.entries.values()})

    async def _program(self):
        b = self.base
        async with self._uow() as uow:
            program = await uow.repositories.programs.create(ProgramInput(name=PROGRAM))
            program.add_trial(TrialInput(name=TRIAL))
            await uow.repositories.programs.update_seen()
            (trial_id,) = program.trials
            program.add_study(trial_id=trial_id, study=StudyInput(
                name=STUDY,
                groupings=[
                    RecordGroupingInput(name=name, type=b[type_key], extent=extent, scope=scope)
                    for name, (type_key, extent, scope) in GROUPINGS.items()
                ]
            ))
            await uow.repositories.programs.update_seen()
            (study_id,) = program.get_trial(trial_id).studies
            study = program.get_study(study_id)
            self.replicates.groupings = {grouping.name: grouping.id for grouping in study.groupings}
            await uow.commit()
        self.replicates.ids.update({'program': program.id, 'trial': trial_id, 'study': study_id})

    async def _dataset(self, key: str):
        concept_key, records = DATASETS[key]
        r = self.replicates
        async with self._uow() as uow:
            stored = await uow.repositories.datasets.create(DatasetInput(
                concept=self.base[concept_key],
                study=r.ids['study'],
                records=[
                    DataRecordInput(
                        unit=r.units[record.unit],
                        value=record.value,
                        start=datetime64(record.start) if record.start else None,
                        groups=[RecordGroup(id=r.groupings[name], code=code) for name, code in record.groups]
                    )
                    for record in records
                ]
            ))
            await uow.commit()
        r.datasets[key] = stored.id

    async def _dataset_scopes(self):
        r = self.replicates
        async with self._uow() as uow:
            program = await uow.repositories.programs.get(program_id=r.ids['program'])
            study = program.get_study(r.ids['study'])
            for name, scopes in DATASET_SCOPES.items():
                grouping = study.get_grouping(grouping_id=r.groupings[name])
                for keys in scopes:
                    grouping.merge_dataset_scope([r.datasets[key] for key in keys])
            await uow.commit()
