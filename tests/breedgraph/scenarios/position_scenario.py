"""
Units at positions in layouts, added to a built read-policy scenario (read_policy_scenario.py), for analysis position
grouping (docs/analysis.md §3; docs/test-databases.md, "The positions"). Fixed names and values, so what analyses report
can be asserted.

Everything is controlled by the child team and REGISTERED, written by the writer. The fields and the greenhouse are
below the read-policy state (child PRIVATE), so viewers outside the child team see them joined to the country (Iran).
The lab is below state_public in country_private (Isle of Man), a hidden root for those viewers.

    Locations                       type              layouts
    state
    ├── Position Field North        Field             Position North Rows (Row, Tree)
    ├── Position Field South        Field             Position South Blocks (Block)
    │                                                 ├── Position South Block 1 (Row, Tree), at Block 1
    │                                                 └── Position South Block 2 (Row, Tree), at Block 2
    ├── Position Field East         Field             Position East 2019 (Row, Tree), a planting with its own rows
    │                                                 Position East 2021 (Row, Tree), another beside it
    └── Position Greenhouse         Research Centre   Position Benches (Bench)
    state_public
    └── Position Lab                Laboratory        Position Freezer (Box, Slot)

    Units                           subject   positions
    Position North                  Field     Field North
    ├── North Tree 1-1              Tree      North Rows 1, 1
    │   └── North Sample            Sample    the lab from 2025-04-01, in the freezer at A, 1
    ├── North Tree 1-2              Tree      North Rows 1, 2
    ├── North Tree 2-1              Tree      North Rows 2, 1
    ├── North Tree 10-1             Tree      North Rows 10, 1
    ├── North Pooled                Sample    from Tree 1-1 and Tree 2-1; the lab from 2025-04-01, freezer A, 2
    └── Moved Tree                  Tree      North Rows 3, 1 to 2024-03-01, then East 2021 2, 1
    Position South                  Field     Field South
    ├── South Tree 1-1              Tree      South Block 1 1, 1
    ├── South Tree 1-2              Tree      South Block 1 1, 2
    └── South Tree 2-1              Tree      South Block 2 1, 1
    Position East                   Field     Field East
    ├── East Tree 2019              Tree      East 2019 1, 1
    └── East Tree 2021              Tree      East 2021 1, 1
    Position Greenhouse Trial       Plot      the greenhouse
    ├── Greenhouse Plant 1          Tree      Bench A to 2024-05-01, then Bench B
    └── Greenhouse Plant 2          Tree      Bench B to 2024-05-01, then Bench A

    Readpolicy positions program > trial > study, with the datasets
        height   the height variable on the trees and plants, each value distinct (HEIGHT)
        width    the width variable on North Sample and North Pooled, measured in the lab (WIDTH)

CASES gives analyses of them and what they report: for each level, the count and mean of the observations, as each
viewer sees them, and the values of the records that are unassigned. Every analysis takes the MEAN of its concept, so
the records of a unit at one place are one observation.
"""
from dataclasses import dataclass, field

from numpy import datetime64

from breedgraph.domain.model.controls import ReadRelease
from breedgraph.domain.model.datasets import DatasetInput, DataRecordInput
from breedgraph.domain.model.layout_trees import LayoutInput
from breedgraph.domain.model.location_trees import LocationInput
from breedgraph.domain.model.programs import ProgramInput, TrialInput, StudyInput
from breedgraph.domain.model.unit_graphs import UnitInput, Position
from breedgraph.service_layer.infrastructure.unit_of_work import AbstractUnitOfWorkFactory

from .read_policy_scenario import ReadPolicyScenario
from .standard_licences import standard_licence_id

PROGRAM = "Readpolicy positions program"
TRIAL = "Readpolicy positions trial"
STUDY = "Readpolicy positions study"

NORTH, SOUTH, EAST = "Position Field North", "Position Field South", "Position Field East"
GREENHOUSE, LAB = "Position Greenhouse", "Position Lab"
# location name: (parent, the read-policy key of the parent or None for one of these, location type key)
LOCATIONS = {
    NORTH: ('state', 'ontology_location_field'),
    SOUTH: ('state', 'ontology_location_field'),
    EAST: ('state', 'ontology_location_field'),
    GREENHOUSE: ('state', 'ontology_location_research_centre'),
    LAB: ('state_public', 'ontology_location_lab'),
}

NORTH_ROWS, SOUTH_BLOCKS, SOUTH_BLOCK_1, SOUTH_BLOCK_2 = (
    "Position North Rows", "Position South Blocks", "Position South Block 1", "Position South Block 2"
)
EAST_2019, EAST_2021, BENCHES, FREEZER = (
    "Position East 2019", "Position East 2021", "Position Benches", "Position Freezer"
)
ROW_AND_TREE = ['Row', 'Tree']
# layout tree roots: name, location, layout type key, axes, then the children: name, type key, axes, position
LAYOUTS = [
    (NORTH_ROWS, NORTH, 'ontology_layout_indexed', ROW_AND_TREE, []),
    (SOUTH_BLOCKS, SOUTH, 'ontology_layout_named', ['Block'], [
        (SOUTH_BLOCK_1, 'ontology_layout_indexed', ROW_AND_TREE, ['1']),
        (SOUTH_BLOCK_2, 'ontology_layout_indexed', ROW_AND_TREE, ['2']),
    ]),
    (EAST_2019, EAST, 'ontology_layout_indexed', ROW_AND_TREE, []),
    (EAST_2021, EAST, 'ontology_layout_indexed', ROW_AND_TREE, []),
    (BENCHES, GREENHOUSE, 'ontology_layout_named', ['Bench'], []),
    (FREEZER, LAB, 'ontology_layout_indexed', ['Box', 'Slot'], []),
]

SAMPLED = '2025-04-01'
MOVED = '2024-03-01'
ROTATED = '2024-05-01'


def at(location: str, layout: str | None = None, coordinates=(), start: str | None = None, end: str | None = None):
    return location, layout, list(coordinates), start, end


# unit name: (subject key, parent names, positions)
UNITS = {
    'Position North': ('ontology_subject_field', [], [at(NORTH)]),
    'North Tree 1-1': ('ontology_subject_tree', ['Position North'], [at(NORTH, NORTH_ROWS, ['1', '1'])]),
    'North Sample': ('ontology_subject_sample', ['North Tree 1-1'], [at(LAB, FREEZER, ['A', '1'], SAMPLED)]),
    'North Tree 1-2': ('ontology_subject_tree', ['Position North'], [at(NORTH, NORTH_ROWS, ['1', '2'])]),
    'North Tree 2-1': ('ontology_subject_tree', ['Position North'], [at(NORTH, NORTH_ROWS, ['2', '1'])]),
    'North Tree 10-1': ('ontology_subject_tree', ['Position North'], [at(NORTH, NORTH_ROWS, ['10', '1'])]),
    'North Pooled': ('ontology_subject_sample', ['North Tree 1-1', 'North Tree 2-1'], [
        at(LAB, FREEZER, ['A', '2'], SAMPLED)
    ]),
    'Moved Tree': ('ontology_subject_tree', ['Position North'], [
        at(NORTH, NORTH_ROWS, ['3', '1'], end=MOVED), at(EAST, EAST_2021, ['2', '1'], start=MOVED)
    ]),
}
SOUTH_UNITS = {
    'Position South': ('ontology_subject_field', [], [at(SOUTH)]),
    'South Tree 1-1': ('ontology_subject_tree', ['Position South'], [at(SOUTH, SOUTH_BLOCK_1, ['1', '1'])]),
    'South Tree 1-2': ('ontology_subject_tree', ['Position South'], [at(SOUTH, SOUTH_BLOCK_1, ['1', '2'])]),
    'South Tree 2-1': ('ontology_subject_tree', ['Position South'], [at(SOUTH, SOUTH_BLOCK_2, ['1', '1'])]),
}
EAST_UNITS = {
    'Position East': ('ontology_subject_field', [], [at(EAST)]),
    'East Tree 2019': ('ontology_subject_tree', ['Position East'], [at(EAST, EAST_2019, ['1', '1'])]),
    'East Tree 2021': ('ontology_subject_tree', ['Position East'], [at(EAST, EAST_2021, ['1', '1'])]),
}
GREENHOUSE_UNITS = {
    'Position Greenhouse Trial': ('ontology_subject_plot', [], [at(GREENHOUSE)]),
    'Greenhouse Plant 1': ('ontology_subject_tree', ['Position Greenhouse Trial'], [
        at(GREENHOUSE, BENCHES, ['A'], end=ROTATED), at(GREENHOUSE, BENCHES, ['B'], start=ROTATED)
    ]),
    'Greenhouse Plant 2': ('ontology_subject_tree', ['Position Greenhouse Trial'], [
        at(GREENHOUSE, BENCHES, ['B'], end=ROTATED), at(GREENHOUSE, BENCHES, ['A'], start=ROTATED)
    ]),
}
UNIT_GRAPHS = [UNITS, SOUTH_UNITS, EAST_UNITS, GREENHOUSE_UNITS]

# dataset: [(unit, value, date)], each value distinct in its dataset
HEIGHT = [
    ('North Tree 1-1', '101', '2024-06-01'), ('North Tree 1-2', '102', '2024-06-01'),
    ('North Tree 2-1', '103', '2024-06-01'), ('North Tree 10-1', '104', '2024-06-01'),
    ('Moved Tree', '105', '2023-06-01'), ('Moved Tree', '303', '2024-06-01'),
    ('South Tree 1-1', '201', '2024-06-01'), ('South Tree 1-2', '202', '2024-06-01'),
    ('South Tree 2-1', '203', '2024-06-01'),
    ('East Tree 2019', '301', '2024-06-01'), ('East Tree 2021', '302', '2024-06-01'),
    ('Greenhouse Plant 1', '400', '2024-04-01'), ('Greenhouse Plant 1', '410', '2024-06-01'),
    ('Greenhouse Plant 2', '420', '2024-04-01'), ('Greenhouse Plant 2', '450', '2024-06-01'),
]
WIDTH = [('North Sample', '11', '2025-04-02'), ('North Pooled', '12', '2025-04-02')]
DATASETS = {'height': ('ontology_variable_height', HEIGHT), 'width': ('ontology_variable_width', WIDTH)}

VIEWERS = ('admin', 'writer', 'stranger', 'outsider')
# the viewers who read the read-policy state and country_private (the child team), and those who don't
CHILD_TEAM, OUTSIDE = ('admin', 'writer'), ('stranger', 'outsider')


@dataclass(frozen=True)
class Level:
    """A level of a position term, by name: a location, or an axis value in the layout that has the axis"""
    location: str | None = None
    layout: str | None = None
    axis: str | None = None
    value: str | None = None


def location(name: str) -> Level:
    return Level(location=name)

def axis(layout_name: str, axis_name: str, value: str) -> Level:
    return Level(layout=layout_name, axis=axis_name, value=value)


@dataclass
class Case:
    """
    An analysis of datasets with position grouping: location types and subjects by read-policy key, and its position
    terms ('LOCATION' or an axis name). expected: viewer: {level: (count, mean)}; unassigned: the values of the
    records it can't place
    """
    key: str
    datasets: list[str]
    location_types: list[str]
    terms: list[str]
    expected: dict[str, dict[Level, tuple[int, float]]]
    unassigned: list[str] = field(default_factory=list)
    subjects: list[str] = field(default_factory=list)
    axes: list[str] = field(default_factory=list)
    time: str | None = None


def everyone(levels: dict[Level, tuple[int, float]]) -> dict[str, dict[Level, tuple[int, float]]]:
    return {viewer: levels for viewer in VIEWERS}

GREENHOUSE_VALUES = ['400', '410', '420', '450']

CASES = [
    # each tree in its field, the moved tree in two; the greenhouse is not a field, nor below one
    Case('fields', ['height'], ['ontology_location_field'], ['LOCATION'], everyone({
        location(NORTH): (5, 103.0), location(SOUTH): (3, 202.0), location(EAST): (3, 302.0),
    }), unassigned=GREENHOUSE_VALUES),
    # at a set time, the moved tree was in field North: its two records are one observation there
    Case('fields_in_2023', ['height'], ['ontology_location_field'], ['LOCATION'], everyone({
        location(NORTH): (5, (101 + 102 + 103 + 104 + (105 + 303) / 2) / 5), location(SOUTH): (3, 202.0),
        location(EAST): (2, 301.5),
    }), unassigned=GREENHOUSE_VALUES, time='2023-01-01'),
    # the samples are in the lab's country, which only the child team reads; others place them by their trees
    Case('countries', ['width'], ['ontology_location_country'], ['LOCATION'], {
        **{viewer: {location('country_private'): (2, 11.5)} for viewer in CHILD_TEAM},
        **{viewer: {location('country'): (2, 11.5)} for viewer in OUTSIDE},
    }),
    Case('countries_by_tree', ['width'], ['ontology_location_country'], ['LOCATION'], everyone({
        location('country'): (2, 11.5),
    }), subjects=['ontology_subject_tree']),
    # rows are nested in their layouts: row 1 of field North is not row 1 of a block or a planting
    Case('rows', ['height'], ['ontology_location_field'], ['Row'], everyone({
        axis(NORTH_ROWS, 'Row', '1'): (2, 101.5), axis(NORTH_ROWS, 'Row', '2'): (1, 103.0),
        axis(NORTH_ROWS, 'Row', '3'): (1, 105.0), axis(NORTH_ROWS, 'Row', '10'): (1, 104.0),
        axis(SOUTH_BLOCK_1, 'Row', '1'): (2, 201.5), axis(SOUTH_BLOCK_2, 'Row', '1'): (1, 203.0),
        axis(EAST_2019, 'Row', '1'): (1, 301.0), axis(EAST_2021, 'Row', '1'): (1, 302.0),
        axis(EAST_2021, 'Row', '2'): (1, 303.0),
    }), unassigned=GREENHOUSE_VALUES, axes=['Row']),
    # the block is an axis of the layout above the blocks' own
    Case('blocks', ['height'], ['ontology_location_field'], ['Block'], everyone({
        axis(SOUTH_BLOCKS, 'Block', '1'): (2, 201.5), axis(SOUTH_BLOCKS, 'Block', '2'): (1, 203.0),
    }), unassigned=['101', '102', '103', '104', '105', '303', '301', '302', *GREENHOUSE_VALUES], axes=['Block']),
    # the plants were rotated: each record is on the bench the plant was on then
    Case('benches', ['height'], ['ontology_location_research_centre'], ['Bench'], everyone({
        axis(BENCHES, 'Bench', 'A'): (2, 425.0), axis(BENCHES, 'Bench', 'B'): (2, 415.0),
    }), unassigned=['101', '102', '103', '104', '105', '303', '201', '202', '203', '301', '302'], axes=['Bench']),
    # in the lab, the box is the samples' own
    Case('freezer', ['width'], ['ontology_location_lab'], ['Box'], everyone({
        axis(FREEZER, 'Box', 'A'): (2, 11.5),
    }), axes=['Box']),
    # by field, a sample takes its tree's row; the pooled one's trees are in two rows
    Case('sample_rows', ['width'], ['ontology_location_field'], ['Row'], everyone({
        axis(NORTH_ROWS, 'Row', '1'): (1, 11.0),
    }), unassigned=['12'], axes=['Row']),
]


@dataclass
class PositionScenario:
    """The ids of what was built, by name"""
    ids: dict[str, int] = field(default_factory=dict)  # program, trial, study
    locations: dict[str, int] = field(default_factory=dict)
    layouts: dict[str, int] = field(default_factory=dict)
    units: dict[str, int] = field(default_factory=dict)
    datasets: dict[str, int] = field(default_factory=dict)  # height, width


class PositionScenarioBuilder:

    def __init__(self, uow_factory: AbstractUnitOfWorkFactory, base: ReadPolicyScenario):
        self.uow_factory = uow_factory
        self.base = base
        self.positions = PositionScenario()

    def _uow(self):
        """The child team's writer"""
        return self.uow_factory.get_uow(
            user_id=self.base['writer'], write_team=self.base['child'], release=ReadRelease.REGISTERED
        )

    async def build(self) -> PositionScenario:
        for name, (parent, type_key) in LOCATIONS.items():
            await self._location(name, parent, type_key)
        for root in LAYOUTS:
            await self._layout_tree(*root)
        for units in UNIT_GRAPHS:
            await self._unit_graph(units)
        await self._study()
        return self.positions

    async def _location(self, name: str, parent: str, type_key: str):
        b = self.base
        async with self._uow() as uow:
            location_tree = await uow.repositories.location_trees.get(location_id=b[parent])
            location_tree.add_location(LocationInput(name=name, type=b[type_key]), parent_id=b[parent])
            await uow.commit()
        async with self.uow_factory.get_uow() as uow:
            location_tree = await uow.repositories.location_trees.get(location_id=b[parent])
            (location_id,) = [location.id for location in location_tree.entries.values() if location.name == name]
        self.positions.locations[name] = location_id

    async def _layout_tree(self, name: str, location_name: str, type_key: str, axes: list[str], children: list):
        b = self.base
        async with self._uow() as uow:
            layout_tree = await uow.repositories.layout_trees.create(LayoutInput(
                name=name, type=b[type_key], location=self.positions.locations[location_name], axes=axes
            ))
            root_id = layout_tree.get_root_id()
            for child_name, child_type_key, child_axes, position in children:
                layout_tree.add_layout(
                    LayoutInput(name=child_name, type=b[child_type_key], axes=child_axes),
                    parent_id=root_id, position=position
                )
            await uow.commit()
        async with self.uow_factory.get_uow() as uow:
            layout_tree = await uow.repositories.layout_trees.get(layout_id=root_id)
            self.positions.layouts.update({layout.name: layout.id for layout in layout_tree.entries.values()})

    def _unit_input(self, name: str, unit: tuple) -> UnitInput:
        subject_key, _, positions = unit
        return UnitInput(
            name=name,
            subject=self.base[subject_key],
            positions=[
                Position(
                    location_id=self.positions.locations[location_name],
                    layout_id=self.positions.layouts[layout_name] if layout_name else None,
                    coordinates=coordinates or None,
                    start=datetime64(start) if start else None,
                    end=datetime64(end) if end else None
                )
                for location_name, layout_name, coordinates, start, end in positions
            ]
        )

    async def _unit_graph(self, units: dict):
        names = list(units)
        async with self._uow() as uow:
            unit_graph = await uow.repositories.unit_graphs.create(self._unit_input(names[0], units[names[0]]))
            temp_ids = {names[0]: unit_graph.get_root_id()}
            for name in names[1:]:
                temp_ids[name] = unit_graph.add_unit(
                    self._unit_input(name, units[name]), parents=[temp_ids[parent] for parent in units[name][1]]
                )
            await uow.commit()
            root_id = unit_graph.get_root_id()
        async with self.uow_factory.get_uow() as uow:
            unit_graph = await uow.repositories.unit_graphs.get(unit_id=root_id)
            self.positions.units.update({unit.name: unit.id for unit in unit_graph.entries.values()})

    async def _study(self):
        b, p = self.base, self.positions
        async with self._uow() as uow:
            program = await uow.repositories.programs.create(ProgramInput(name=PROGRAM))
            program.add_trial(TrialInput(name=TRIAL))
            await uow.repositories.programs.update_seen()
            (trial_id,) = program.trials
            licence_id = await standard_licence_id(self.uow_factory)
            program.add_study(trial_id=trial_id, study=StudyInput(name=STUDY, licence_id=licence_id))
            await uow.repositories.programs.update_seen()
            (study_id,) = program.get_trial(trial_id).studies
            await uow.commit()
        p.ids.update({'program': program.id, 'trial': trial_id, 'study': study_id})
        for key, (concept_key, records) in DATASETS.items():
            async with self._uow() as uow:
                stored = await uow.repositories.datasets.create(DatasetInput(
                    concept=b[concept_key],
                    study=study_id,
                    records=[
                        DataRecordInput(unit=p.units[unit], value=value, start=datetime64(start))
                        for unit, value, start in records
                    ]
                ))
                await uow.commit()
            p.datasets[key] = stored.id


def level_key(positions: PositionScenario, base: ReadPolicyScenario, level: Level) -> str:
    """The level as analysis results give it (docs/analysis.md §6): a location id, or layoutId|value"""
    if level.location is not None:
        return str(positions.locations.get(level.location) or base[level.location])
    return f"{positions.layouts[level.layout]}|{level.value}"


def grouping_input(case: Case, base: ReadPolicyScenario) -> dict:
    """The case's position grouping as GraphQL input"""
    grouping = {'locationTypeIds': [base[key] for key in case.location_types]}
    if case.subjects:
        grouping['subjectIds'] = [base[key] for key in case.subjects]
    if case.axes:
        grouping['axes'] = case.axes
    if case.time:
        grouping['time'] = case.time
    return grouping


def term_inputs(case: Case) -> list[dict]:
    return [
        {'reference': {'type': 'LOCATION'}} if term == 'LOCATION'
        else {'reference': {'type': 'LAYOUT_AXIS', 'layoutAxis': term}}
        for term in case.terms
    ]
