"""
Units that came to locations at dated positions, added to a built read-policy scenario (read_policy_scenario.py), for
the arrivals of breedview's Units page (docs/test-databases.md, "The arrivals scenario"), moving units in bulk, and
germplasm and factors coming down the unit graph. Fixed names, so the arrivals and what is inherited can be asserted.

Everything is controlled by the child team and REGISTERED, written by the writer, except Arrival Sample Hidden, which is
PRIVATE: the admin and the writer read it, other signed-in users do not; anonymous users read none of it; and the
derived units below, which the stranger's other team controls, REGISTERED.

    Arrival Lab Store                a location below lab

    Arrival Field                    Field     at field_registered
    └── Arrival Plot                 Plot
        ├── Arrival Tree A           Tree      germplasm crop_leaf; light 100
        │   ├── Arrival Sample A1    Sample    at lab from 2025-03-25
        │   │   └── Arrival Extract A1  Sample at lab from 2025-04-01: taken at the lab, so not an arrival
        │   ├── Arrival Sample A2    Sample    at lab from 2025-03-25 to 2025-05-02, then at Arrival Lab Store
        │   ├── Arrival Sample A3    Sample    at lab from 2025-03-25 to 2025-04-15: used up
        │   ├── Arrival Sample Hidden  Sample  PRIVATE; germplasm crop_line_public; at lab from 2025-03-25
        │   │   └── Arrival Extract Hidden  Sample  at lab from 2025-03-25: an arrival for whoever can't read its sample
        │   ├── Arrival Sample Own   Sample    germplasm crop_line, its own; at lab from 2024-11
        │   └── Arrival Pooled       Sample    from Tree A and Tree B; at lab from 2025-03-25
        ├── Arrival Tree B           Tree      germplasm crop_private_child; light 200;
        │   │                                  at lab from 2024-06 to 2024-07, then back at field_registered
        │   └── Arrival Sample B1    Sample    at lab from 2025-03-25: arrived after its tree's visit, on its own
        │   (and Arrival Pooled)
        ├── Arrival Tree C           Tree      germplasm crop_leaf; light 100
        │   ├── Arrival Leaf C       Leaf      with its tree
        │   ├── Arrival Cuttings C   Sample    microcuttings, at lab from 2025-02-10: derived from, so settled there
        │   └── Arrival Pooled Same  Sample    from Tree A and Tree C; at lab, undated
        └── Arrival Move Tree        Tree
            ├── Arrival Move Sample 1  Sample  at lab from 2025-06-10
            └── Arrival Move Sample 2  Sample  at lab from 2025-06-10

    Arrival Field Season 2025        Field     the stranger's, at field_registered from 2025-01
    └── Arrival Plantlet C           Tree      derived from Arrival Cuttings C (PLANTLET, micropropagation), at
                                               field_registered from 2025-03-15; germplasm crop_leaf, copied from the
                                               cuttings when derived, as nothing comes down a derivation

    Readpolicy arrivals program > trial > study, with the datasets
        light    the light factor on Tree A (100), Tree B (200) and Tree C (100), undated
        height   the height variable on Sample A1, Sample B1, Arrival Pooled and Arrival Pooled Same, on 2025-03-26

EXPECTED_ARRIVALS gives each location's arrivals as each viewer sees them, expected_germplasm the germplasm each unit
takes, its own or that of the nearest units above it (by their read-policy names), and EXPECTED_LIGHT the light that
describes each height record: Arrival Pooled takes none, its trees' records differing.
"""
from dataclasses import dataclass, field

from numpy import datetime64

from breedgraph.domain.model.controls import ReadRelease
from breedgraph.domain.model.datasets import DatasetInput, DataRecordInput
from breedgraph.domain.model.location_trees import LocationInput
from breedgraph.domain.model.programs import ProgramInput, TrialInput, StudyInput
from breedgraph.domain.model.unit_graphs import UnitInput, Position, UnitDerivation, DerivationStage
from breedgraph.service_layer.infrastructure.unit_of_work import AbstractUnitOfWorkFactory

from .read_policy_scenario import ReadPolicyScenario
from .standard_licences import standard_licence_id

PROGRAM = "Readpolicy arrivals program"
TRIAL = "Readpolicy arrivals trial"
STUDY = "Readpolicy arrivals study"
LAB_STORE = "Arrival Lab Store"

LAB, STORE, FIELD = 'lab', 'lab_store', 'field_registered'


def at(location: str, start: str | None = None, end: str | None = None) -> tuple:
    return location, start, end


# unit name: (subject key, parent names, germplasm key, positions as (location, start, end))
UNITS = {
    'Arrival Field': ('ontology_subject_field', [], None, [at(FIELD)]),
    'Arrival Plot': ('ontology_subject_plot', ['Arrival Field'], None, []),
    'Arrival Tree A': ('ontology_subject_tree', ['Arrival Plot'], 'crop_leaf', []),
    'Arrival Sample A1': ('ontology_subject_sample', ['Arrival Tree A'], None, [at(LAB, '2025-03-25')]),
    'Arrival Extract A1': ('ontology_subject_sample', ['Arrival Sample A1'], None, [at(LAB, '2025-04-01')]),
    'Arrival Sample A2': ('ontology_subject_sample', ['Arrival Tree A'], None, [
        at(LAB, '2025-03-25', '2025-05-02'), at(STORE, '2025-05-02')
    ]),
    'Arrival Sample A3': ('ontology_subject_sample', ['Arrival Tree A'], None, [at(LAB, '2025-03-25', '2025-04-15')]),
    'Arrival Sample Own': ('ontology_subject_sample', ['Arrival Tree A'], 'crop_line', [at(LAB, '2024-11')]),
    'Arrival Tree B': ('ontology_subject_tree', ['Arrival Plot'], 'crop_private_child', [
        at(LAB, '2024-06', '2024-07'), at(FIELD, '2024-07')
    ]),
    'Arrival Sample B1': ('ontology_subject_sample', ['Arrival Tree B'], None, [at(LAB, '2025-03-25')]),
    'Arrival Pooled': ('ontology_subject_sample', ['Arrival Tree A', 'Arrival Tree B'], None, [at(LAB, '2025-03-25')]),
    'Arrival Tree C': ('ontology_subject_tree', ['Arrival Plot'], 'crop_leaf', []),
    'Arrival Leaf C': ('ontology_subject_leaf', ['Arrival Tree C'], None, []),
    'Arrival Cuttings C': ('ontology_subject_sample', ['Arrival Tree C'], None, [at(LAB, '2025-02-10')]),
    'Arrival Pooled Same': ('ontology_subject_sample', ['Arrival Tree A', 'Arrival Tree C'], None, [at(LAB)]),
    'Arrival Move Tree': ('ontology_subject_tree', ['Arrival Plot'], None, []),
    'Arrival Move Sample 1': ('ontology_subject_sample', ['Arrival Move Tree'], None, [at(LAB, '2025-06-10')]),
    'Arrival Move Sample 2': ('ontology_subject_sample', ['Arrival Move Tree'], None, [at(LAB, '2025-06-10')]),
}
# added after the unit graph, each in a unit of work of its own release
HIDDEN = {
    'Arrival Sample Hidden': (ReadRelease.PRIVATE, ('ontology_subject_sample', ['Arrival Tree A'], 'crop_line_public', [
        at(LAB, '2025-03-25')
    ])),
    'Arrival Extract Hidden': (ReadRelease.REGISTERED, ('ontology_subject_sample', ['Arrival Sample Hidden'], None, [
        at(LAB, '2025-03-25')
    ])),
}
RELEASES = {name: ReadRelease.REGISTERED for name in UNITS} | {name: release for name, (release, _) in HIDDEN.items()}
# a unit graph of the stranger's, in the other team and REGISTERED: the field season the cuttings were planted in, and
# the plantlet derived from them (README, Unit), with the germplasm the cuttings take from their tree as its own
SEASON, PLANTLET = 'Arrival Field Season 2025', 'Arrival Plantlet C'
DERIVED = {
    SEASON: ('ontology_subject_field', [], None, [at(FIELD, '2025-01')]),
    PLANTLET: ('ontology_subject_tree', [SEASON], 'crop_leaf', [at(FIELD, '2025-03-15')]),
}
# derived unit: (the unit it came from, the stage it was at, description)
DERIVATIONS = {PLANTLET: ('Arrival Cuttings C', DerivationStage.PLANTLET, 'Micropropagation')}
RELEASES |= {name: ReadRelease.REGISTERED for name in DERIVED}

# location: the arrivals there, newest first and undated last, as (start, unit names by name)
_LAB_WRITER = [
    ('2025-06-10', ['Arrival Move Sample 1', 'Arrival Move Sample 2']),
    ('2025-03-25', ['Arrival Pooled', 'Arrival Sample A1', 'Arrival Sample A2', 'Arrival Sample A3',
                    'Arrival Sample B1', 'Arrival Sample Hidden']),
    ('2025-02-10', ['Arrival Cuttings C']),
    ('2024-11', ['Arrival Sample Own']),
    ('2024-06', ['Arrival Tree B']),
    (None, ['Arrival Pooled Same']),
]
_LAB_REGISTERED = [
    ('2025-06-10', ['Arrival Move Sample 1', 'Arrival Move Sample 2']),
    ('2025-03-25', ['Arrival Extract Hidden', 'Arrival Pooled', 'Arrival Sample A1', 'Arrival Sample A2',
                    'Arrival Sample A3', 'Arrival Sample B1']),
    ('2025-02-10', ['Arrival Cuttings C']),
    ('2024-11', ['Arrival Sample Own']),
    ('2024-06', ['Arrival Tree B']),
    (None, ['Arrival Pooled Same']),
]
_STORE = [('2025-05-02', ['Arrival Sample A2'])]
EXPECTED_ARRIVALS = {
    LAB: {'admin': _LAB_WRITER, 'writer': _LAB_WRITER, 'stranger': _LAB_REGISTERED, 'outsider': _LAB_REGISTERED,
          'anonymous': []},
    STORE: {'admin': _STORE, 'writer': _STORE, 'stranger': _STORE, 'outsider': _STORE, 'anonymous': []},
    # back at its field, Tree B is with its parents, so the field has no arrivals
    FIELD: {viewer: [] for viewer in ('admin', 'writer', 'stranger', 'outsider', 'anonymous')},
}

# unit name: (germplasm key, the units it may come from, the nearest by distance and then id), as the admin and writer
# see it; None for none
_GERMPLASM = {
    'Arrival Tree A': ('crop_leaf', ['Arrival Tree A']),
    'Arrival Sample A1': ('crop_leaf', ['Arrival Tree A']),
    'Arrival Extract A1': ('crop_leaf', ['Arrival Tree A']),
    'Arrival Sample A2': ('crop_leaf', ['Arrival Tree A']),
    'Arrival Sample A3': ('crop_leaf', ['Arrival Tree A']),
    'Arrival Sample Hidden': ('crop_line_public', ['Arrival Sample Hidden']),
    'Arrival Extract Hidden': ('crop_line_public', ['Arrival Sample Hidden']),
    'Arrival Sample Own': ('crop_line', ['Arrival Sample Own']),
    'Arrival Tree B': ('crop_private_child', ['Arrival Tree B']),
    'Arrival Sample B1': ('crop_private_child', ['Arrival Tree B']),
    'Arrival Pooled': None,  # crop_leaf from Tree A, crop_private_child from Tree B
    'Arrival Tree C': ('crop_leaf', ['Arrival Tree C']),
    'Arrival Leaf C': ('crop_leaf', ['Arrival Tree C']),
    'Arrival Cuttings C': ('crop_leaf', ['Arrival Tree C']),
    # its own, copied from the cuttings when it was derived from them
    'Arrival Plantlet C': ('crop_leaf', ['Arrival Plantlet C']),
    'Arrival Field Season 2025': None,
    'Arrival Pooled Same': ('crop_leaf', ['Arrival Tree A', 'Arrival Tree C']),  # the two trees agree
    'Arrival Move Tree': None,
    'Arrival Move Sample 1': None,
    'Arrival Move Sample 2': None,
}
# signed-in users outside the child team don't read the hidden sample, so its extract, the nearest unit with germplasm
# above which is hidden from them, takes none
_GERMPLASM_REGISTERED = {name: value for name, value in _GERMPLASM.items() if name != 'Arrival Sample Hidden'} \
    | {'Arrival Extract Hidden': None}
GERMPLASM_BY_VIEWER = {
    'admin': _GERMPLASM, 'writer': _GERMPLASM, 'stranger': _GERMPLASM_REGISTERED, 'outsider': _GERMPLASM_REGISTERED
}


def expected_germplasm(arrivals: 'ArrivalScenario', viewer: str) -> dict:
    """unit name: {germplasm: read-policy key, unit: the unit it comes from} as the viewer sees it, or None"""
    return {
        name: None if value is None else {
            'germplasm': value[0],
            'unit': min(value[1], key=lambda source: arrivals.units[source])
        }
        for name, value in GERMPLASM_BY_VIEWER[viewer].items()
    }


LIGHT = {'Arrival Tree A': '100', 'Arrival Tree B': '200', 'Arrival Tree C': '100'}
HEIGHT = {'Arrival Sample A1': '11', 'Arrival Sample B1': '12', 'Arrival Pooled': '13', 'Arrival Pooled Same': '14'}
HEIGHT_DATE = '2025-03-26'
# height record's unit: the light that describes it, from the trees above it; Arrival Pooled's trees differ
EXPECTED_LIGHT = {'Arrival Sample A1': '100', 'Arrival Sample B1': '200', 'Arrival Pooled': None,
                  'Arrival Pooled Same': '100'}


@dataclass
class ArrivalScenario:
    """The ids of what was built, by name"""
    ids: dict[str, int] = field(default_factory=dict)  # program, trial, study, lab_store
    units: dict[str, int] = field(default_factory=dict)
    datasets: dict[str, int] = field(default_factory=dict)  # light, height


class ArrivalScenarioBuilder:

    def __init__(self, uow_factory: AbstractUnitOfWorkFactory, base: ReadPolicyScenario):
        self.uow_factory = uow_factory
        self.base = base
        self.arrivals = ArrivalScenario()

    def _uow(self, release: ReadRelease = ReadRelease.REGISTERED):
        """The child team's writer"""
        return self.uow_factory.get_uow(user_id=self.base['writer'], write_team=self.base['child'], release=release)

    async def build(self) -> ArrivalScenario:
        await self._lab_store()
        await self._unit_graph()
        for name, (release, unit) in HIDDEN.items():
            await self._unit(name, unit, release)
        await self._derived()
        await self._study()
        return self.arrivals

    def _location_id(self, key: str) -> int:
        return self.arrivals.ids[key] if key == STORE else self.base[key]

    def _unit_input(self, name: str, unit: tuple) -> UnitInput:
        subject_key, _, germplasm_key, positions = unit
        return UnitInput(
            name=name,
            subject=self.base[subject_key],
            germplasm=self.base[germplasm_key] if germplasm_key else None,
            positions=[
                Position(
                    location_id=self._location_id(location),
                    start=datetime64(start) if start else None,
                    end=datetime64(end) if end else None
                )
                for location, start, end in positions
            ]
        )

    async def _lab_store(self):
        b = self.base
        async with self._uow() as uow:
            location_tree = await uow.repositories.location_trees.get(location_id=b['lab'])
            location_tree.add_location(LocationInput(name=LAB_STORE, type=b['ontology_location_lab']), parent_id=b['lab'])
            await uow.commit()
        async with self.uow_factory.get_uow() as uow:
            location_tree = await uow.repositories.location_trees.get(location_id=b['lab'])
            (store,) = [location.id for location in location_tree.entries.values() if location.name == LAB_STORE]
        self.arrivals.ids[STORE] = store

    async def _unit_graph(self):
        names = list(UNITS)
        async with self._uow() as uow:
            unit_graph = await uow.repositories.unit_graphs.create(self._unit_input(names[0], UNITS[names[0]]))
            temp_ids = {names[0]: unit_graph.get_root_id()}
            for name in names[1:]:
                parents = UNITS[name][1]
                temp_ids[name] = unit_graph.add_unit(
                    self._unit_input(name, UNITS[name]), parents=[temp_ids[parent] for parent in parents]
                )
            await uow.commit()
            root_id = unit_graph.get_root_id()
        async with self.uow_factory.get_uow() as uow:
            unit_graph = await uow.repositories.unit_graphs.get(unit_id=root_id)
            self.arrivals.units.update({unit.name: unit.id for unit in unit_graph.entries.values()})

    async def _unit(self, name: str, unit: tuple, release: ReadRelease):
        parents = [self.arrivals.units[parent] for parent in unit[1]]
        async with self._uow(release) as uow:
            unit_graph = await uow.repositories.unit_graphs.get(unit_id=parents[0])
            unit_graph.add_unit(self._unit_input(name, unit), parents=parents)
            await uow.commit()
        async with self.uow_factory.get_uow() as uow:
            unit_graph = await uow.repositories.unit_graphs.get(unit_id=parents[0])
            (unit_id,) = [u.id for u in unit_graph.entries.values() if u.name == name]
        self.arrivals.units[name] = unit_id

    async def _derived(self):
        """The stranger's field season, and the plantlet derived from the cuttings that arrived at the lab"""
        b = self.base
        async with self.uow_factory.get_uow(
                user_id=b['stranger'], write_team=b['other'], release=ReadRelease.REGISTERED
        ) as uow:
            unit_graph = await uow.repositories.unit_graphs.create(self._unit_input(SEASON, DERIVED[SEASON]))
            for name, unit in DERIVED.items():
                if name == SEASON:
                    continue
                unit_input = self._unit_input(name, unit)
                if name in DERIVATIONS:
                    source, stage, description = DERIVATIONS[name]
                    unit_input.derived_from = [UnitDerivation(
                        unit_id=self.arrivals.units[source], stage=stage, description=description
                    )]
                unit_graph.add_unit(unit_input, parents=[unit_graph.get_root_id()])
            await uow.commit()
            root_id = unit_graph.get_root_id()
        async with self.uow_factory.get_uow() as uow:
            unit_graph = await uow.repositories.unit_graphs.get(unit_id=root_id)
            self.arrivals.units.update({unit.name: unit.id for unit in unit_graph.entries.values()})

    async def _study(self):
        b, a = self.base, self.arrivals
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
        a.ids.update({'program': program.id, 'trial': trial_id, 'study': study_id})
        for key, concept_key, values, start in (
                ('light', 'ontology_factor_light', LIGHT, None),
                ('height', 'ontology_variable_height', HEIGHT, HEIGHT_DATE),
        ):
            async with self._uow() as uow:
                stored = await uow.repositories.datasets.create(DatasetInput(
                    concept=b[concept_key],
                    study=study_id,
                    records=[
                        DataRecordInput(unit=a.units[unit], value=value, start=datetime64(start) if start else None)
                        for unit, value in values.items()
                    ]
                ))
                await uow.commit()
            a.datasets[key] = stored.id
