"""
The read-policy scenario: one world for the read tests (docs/read-access.md) and for the synthetic test database.

Viewers and teams. "root" is a team tree root with a child team "child"; "other" is a second team tree.

    admin     WRITE, READ, CURATE, ADMIN on root; ADMIN and READ on child (no WRITE, no CURATE)
    writer    READ, WRITE, CURATE on child
    stranger  every access on other; nothing in root or child
    outsider  registered, in no team
    anonymous no user

Each entity below is listed with its controlling team, release and writer. Hidden members sit between readable ones,
so each viewer sees a skip, a placeholder or a reconnection somewhere (rules 2 to 4).

Location trees
    country                      root  PUBLIC      admin
    └── state                    child PRIVATE     writer
        ├── field                child PUBLIC      writer
        │   └── centre           other PRIVATE     stranger
        │       └── lab          other REGISTERED  stranger
        └── field_registered     child REGISTERED  writer
    country_private              child PRIVATE     writer    (a hidden location tree root)
    └── state_public             child PUBLIC      writer

Layout trees
    facility                     root  PUBLIC      admin     (at field)
    └── chamber                  child PRIVATE     writer
        └── shelf                child PUBLIC      writer
    facility_private             child PRIVATE     writer    (at state; a hidden layout tree root)
    └── room_public              child PUBLIC      writer

Units
    field_unit                   child PRIVATE     writer    (a hidden unit graph root, at field)
    ├── tree_public              child PUBLIC      writer    (also at state; germplasm crop_leaf)
    │   ├── leaf_private         child PRIVATE     writer
    │   │   └── rhizosphere_public  child PUBLIC   writer
    │   └── leaf_other           other PRIVATE     stranger
    │       └── rhizosphere_other   other REGISTERED stranger
    └── tree_registered          child REGISTERED  writer    (germplasm crop_middle)
    plot_public                  root  PUBLIC      admin     (at field_registered)
    └── plant_private            child PRIVATE     writer
    plot_private                 child PRIVATE     writer    (at field; a hidden root holding nothing readable)

Programs
    program                      child PRIVATE     writer
    └── trial                    child PRIVATE     writer
        ├── study_public         child PUBLIC      writer
        └── study_private        child PRIVATE     writer
    program_public               root  PUBLIC      admin
    └── trial_public             root  PUBLIC      admin
        └── study_registered     root  REGISTERED  admin

References (descriptions all contain "Readpolicy"; each file is a small CSV in the file store)
    reference_public             root  PUBLIC      admin     (file reference)
    reference_private            child PRIVATE     writer    (file reference)
    reference_registered         root  REGISTERED  admin     (legal reference)
    reference_legal_private      child PRIVATE     writer    (legal reference)
    study_public cites reference_public and reference_private

People
    person_admin                 root  PUBLIC      admin     teams [root]; linked to the admin
    person_public                child PUBLIC      writer    teams [root, child]
    person_private               child PRIVATE     writer    teams [child]
    person_other                 other REGISTERED  stranger  teams [other]
    person_outsider              child PRIVATE     writer    teams [child]; linked to the outsider
    person_claimed               child PRIVATE     writer    teams [child]; the outsider asks to be linked

Datasets (concept: the tree height variable)
    dataset_public               child PUBLIC      writer    study_public; records on tree_public, leaf_private,
                                                             rhizosphere_public, tree_registered;
                                                             contributors person_public, person_private;
                                                             references reference_public
    dataset_private              child PRIVATE     writer    study_public; a record on tree_public
    dataset_registered           root  REGISTERED  admin     study_registered; a record on tree_public citing
                                                             reference_private; contributor person_private

Ontology: the builders' types and variables, all active; then a commit by the admin citing reference_registered as
its licence and reference_legal_private as its copyright; then ontology_subject_draft, a subject left in draft

Germplasm (each link from a source, SEED unless given)
    crop                         root  PUBLIC      admin
    └── crop_middle              child PRIVATE     writer
        └── crop_leaf            root  PUBLIC      admin
            ├── crop_line        child REGISTERED  writer
            │   └── crop_line_public  root PUBLIC  admin
            └── crop_other       other PRIVATE     stranger
                └── crop_other_child  other REGISTERED stranger
    crop_private                 child PRIVATE     writer    (a hidden crop)
    └── crop_private_child       root  PUBLIC      admin
    hybrid                       root  PUBLIC      admin     sources crop_leaf (MATERNAL), crop_private (PATERNAL)
"""
import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple

from breedgraph import config
from breedgraph.domain.model.accounts import OntologyRole, AccountInput, UserInput
from breedgraph.domain.model.ontology import VersionChange
from breedgraph.domain.model.archive import FileArchivalRecord, ArchiveState, LocalState
from breedgraph.domain.model.layout_trees import LayoutInput
from breedgraph.domain.model.unit_graphs import UnitInput, Position
from breedgraph.domain.model.controls import Access, ReadRelease, ControlledModelLabel
from breedgraph.domain.model.datasets import DatasetInput, DataRecordInput
from breedgraph.domain.model.germplasm import GermplasmInput, GermplasmRelationship, GermplasmSourceType
from breedgraph.domain.model.team_trees import TeamInput
from breedgraph.domain.model.people import PersonInput
from breedgraph.domain.model.programs import TrialInput
from breedgraph.domain.model.references import FileReferenceInput, LegalReferenceInput
from breedgraph.domain.model.location_trees import LocationInput
from breedgraph.service_layer.infrastructure.archival_service import AbstractFileArchivalService
from breedgraph.service_layer.infrastructure.state_store import AbstractStateStore
from breedgraph.service_layer.infrastructure.unit_of_work import AbstractUnitOfWorkFactory

from tests.breedgraph.utilities.inputs import LoremTextGenerator, UserInputGenerator

from .account_builder import AccountBuilder
from .authorisation_manager import AuthorisationManager
from .ontology_builder import OntologyBuilder
from .team_tree_builder import TeamTreeBuilder
from .program_builder import ProgramBuilder
from .location_tree_builder import LocationTreeBuilder

PUBLIC, REGISTERED, PRIVATE = ReadRelease.PUBLIC, ReadRelease.REGISTERED, ReadRelease.PRIVATE

VIEWERS = ('admin', 'writer', 'stranger', 'outsider', 'anonymous')

# The trees by name, each member to its parent, as built
LOCATION_PARENTS = {
    'country': None, 'state': 'country', 'field': 'state', 'centre': 'field', 'lab': 'centre',
    'field_registered': 'state', 'country_private': None, 'state_public': 'country_private'
}
LAYOUT_PARENTS = {
    'facility': None, 'chamber': 'facility', 'shelf': 'chamber',
    'facility_private': None, 'room_public': 'facility_private'
}
UNIT_PARENTS = {
    'field_unit': None, 'tree_public': 'field_unit', 'leaf_private': 'tree_public',
    'rhizosphere_public': 'leaf_private', 'leaf_other': 'tree_public', 'rhizosphere_other': 'leaf_other',
    'tree_registered': 'field_unit',
    'plot_public': None, 'plant_private': 'plot_public',
    'plot_private': None
}

# The datasets by name, as built: each record is (unit, value, references cited by the record)
DATASETS = {
    'dataset_public': {
        'study': 'study_public',
        'records': [('tree_public', '1', []), ('leaf_private', '2', []), ('rhizosphere_public', '3', []),
                    ('tree_registered', '4', [])],
        'contributors': ['person_public', 'person_private'],
        'references': ['reference_public'],
    },
    'dataset_private': {
        'study': 'study_public',
        'records': [('tree_public', '10', [])],
        'contributors': [],
        'references': [],
    },
    'dataset_registered': {
        'study': 'study_registered',
        'records': [('tree_public', '20', ['reference_private'])],
        'contributors': ['person_private'],
        'references': [],
    },
}

# The germplasm entries by name, in build order: (team, release, [(source, source type)])
GERMPLASM = {
    'crop': ('root', PUBLIC, []),
    'crop_middle': ('child', PRIVATE, [('crop', 'SEED')]),
    'crop_leaf': ('root', PUBLIC, [('crop_middle', 'SEED')]),
    'crop_line': ('child', REGISTERED, [('crop_leaf', 'SEED')]),
    'crop_line_public': ('root', PUBLIC, [('crop_line', 'SEED')]),
    'crop_other': ('other', PRIVATE, [('crop_leaf', 'SEED')]),
    'crop_other_child': ('other', REGISTERED, [('crop_other', 'SEED')]),
    'crop_private': ('child', PRIVATE, []),
    'crop_private_child': ('root', PUBLIC, [('crop_private', 'SEED')]),
    'hybrid': ('root', PUBLIC, [('crop_leaf', 'MATERNAL'), ('crop_private', 'PATERNAL')]),
}

# The Persons by name, as built: (team, release, teams, linked user, user asking to be linked)
PEOPLE = {
    'person_admin': ('root', PUBLIC, ['root'], 'admin', None),
    'person_public': ('child', PUBLIC, ['root', 'child'], None, None),
    'person_private': ('child', PRIVATE, ['child'], None, None),
    'person_other': ('other', REGISTERED, ['other'], None, None),
    'person_outsider': ('child', PRIVATE, ['child'], 'outsider', None),
    'person_claimed': ('child', PRIVATE, ['child'], None, 'outsider'),
}

# The references by name, as built: (type, description); the files' ids and contents are in ReadPolicyScenario.files
REFERENCES = {
    'reference_public': ('FILE', 'Readpolicy public file'),
    'reference_private': ('FILE', 'Readpolicy private file'),
    'reference_registered': ('LEGAL', 'Readpolicy registered licence'),
    'reference_legal_private': ('LEGAL', 'Readpolicy private licence'),
}
STUDY_REFERENCES = {'study_public': ['reference_public', 'reference_private']}

# The programs, trials and studies by name, as built
PROGRAMS = {
    'program': {'trial': ['study_public', 'study_private']},
    'program_public': {'trial_public': ['study_registered']},
}

text = LoremTextGenerator()
users = UserInputGenerator()


# The label of every controlled entity in the scenario, by name
ENTITY_LABELS = {
    **{name: ControlledModelLabel.LOCATION for name in LOCATION_PARENTS},
    **{name: ControlledModelLabel.LAYOUT for name in LAYOUT_PARENTS},
    **{name: ControlledModelLabel.UNIT for name in UNIT_PARENTS},
    **{name: ControlledModelLabel.PROGRAM for name in PROGRAMS},
    **{trial: ControlledModelLabel.TRIAL for trials in PROGRAMS.values() for trial in trials},
    **{study: ControlledModelLabel.STUDY for trials in PROGRAMS.values() for studies in trials.values() for study in studies},
    **{name: ControlledModelLabel.DATASET for name in DATASETS},
    **{name: ControlledModelLabel.REFERENCE for name in REFERENCES},
    **{name: ControlledModelLabel.PERSON for name in PEOPLE},
    **{name: ControlledModelLabel.GERMPLASM for name in GERMPLASM},
}

# What each signed-in viewer's affiliations give them, by team
AFFILIATIONS = {
    'admin': {'root': set(Access), 'child': {Access.ADMIN, Access.READ}},
    'writer': {'child': {Access.READ, Access.WRITE, Access.CURATE}},
    'stranger': {'other': set(Access)},
    'outsider': {},
}


@dataclass
class TreeMember:
    """
    A member of a tree as a viewer should see it (rules 3 and 4): readable, or a root kept as a placeholder, or a bare
    placeholder (no parent, no children) for any other hidden member asked for by id
    """
    readable: bool
    root: str
    parent: str | None
    children: set[str]


@dataclass
class GermplasmEntryView:
    """A germplasm entry as a viewer should see it: its sources and sinks by name, each with its source type"""
    readable: bool
    sources: dict[str, str]
    sinks: dict[str, str]


@dataclass
class ReadPolicyScenario:
    """
    The ids of the scenario's users, teams and entities, by the names in the module docstring,
    and the controls each entity was written under, so tests can ask who reads what.
    """
    ids: Dict[str, int] = field(default_factory=dict)
    controls: Dict[str, Tuple[str, ReadRelease]] = field(default_factory=dict)
    files: Dict[str, Tuple[str, bytes]] = field(default_factory=dict)  # file references by name: (file id, content)
    read_teams: Dict[str, set[str]] = field(default_factory=lambda: {
        'admin': {'root', 'child'},
        'writer': {'child'},
        'stranger': {'other'},
        'outsider': set(),
        'anonymous': set()
    })

    def __getitem__(self, name: str) -> int:
        return self.ids[name]

    def user(self, viewer: str) -> int | None:
        """The user id of a viewer, None for anonymous"""
        return None if viewer == 'anonymous' else self.ids[viewer]

    def readable(self, viewer: str, name: str) -> bool:
        """Whether the viewer can read the entity, by section 1 of docs/read-access.md"""
        team, release = self.controls[name]
        if team in self.read_teams[viewer]:
            return True
        return release >= (PUBLIC if viewer == 'anonymous' else REGISTERED)

    def tree_member(self, viewer: str, parents: dict[str, str | None], name: str) -> TreeMember:
        """
        How the viewer should see a member of the tree given by parents: hidden members skipped, so a readable
        member's parent is its nearest readable ancestor or else the root, which is always kept, and the children of
        a readable member or a root are its nearest readable descendants, found through hidden members only
        """
        root = name
        while parents[root] is not None:
            root = parents[root]
        readable = self.readable(viewer, name)
        if not readable and name != root:
            return TreeMember(readable=False, root=root, parent=None, children=set())

        parent = parents[name]
        while parent is not None and parent != root and not self.readable(viewer, parent):
            parent = parents[parent]

        children = set()
        pending = [member for member, member_parent in parents.items() if member_parent == name]
        while pending:
            member = pending.pop()
            if self.readable(viewer, member):
                children.add(member)
            else:
                pending.extend(below for below, below_parent in parents.items() if below_parent == member)
        return TreeMember(readable=readable, root=root, parent=parent, children=children)

    def shown_roots(self, viewer: str, parents: dict[str, str | None]) -> set[str]:
        """The roots of the trees in which the viewer can read a member"""
        return {
            self.tree_member(viewer, parents, name).root for name in parents if self.readable(viewer, name)
        }

    def recorded_unit_level(
            self, viewer: str, datasets: list[str], parent: str | None = None
    ) -> dict[str, tuple[int, int, bool]]:
        """
        One level of the tree of the units the datasets have records for, as the viewer should see it (section 3 of
        docs/read-access.md), as {unit: (unit_count, record_count, has_children)}: the roots, or the children of
        parent. A readable unit counts the recorded units at and below it, a hidden one only itself. Roots are the
        readable or recorded units with no readable ancestor; children are reached from a readable parent through
        hidden units only, and a hidden parent has none. Units counting nothing are left out.
        """
        records = [(dataset, unit) for dataset in datasets for unit, _, _ in DATASETS[dataset]['records']]
        recorded = {unit for _, unit in records}

        def below(unit: str) -> set[str]:
            found, pending = set(), [unit]
            while pending:
                current = pending.pop()
                children = [member for member, member_parent in UNIT_PARENTS.items() if member_parent == current]
                found.update(children)
                pending.extend(children)
            return found

        def counted(unit: str) -> set[str]:
            return recorded & ({unit} | below(unit) if self.readable(viewer, unit) else {unit})

        def ancestors(unit: str) -> set[str]:
            found, member = set(), UNIT_PARENTS[unit]
            while member is not None:
                found.add(member)
                member = UNIT_PARENTS[member]
            return found

        if parent is None:
            candidates = {
                unit for unit in UNIT_PARENTS
                if (self.readable(viewer, unit) or unit in recorded)
                and not any(self.readable(viewer, ancestor) for ancestor in ancestors(unit))
            }
        elif not self.readable(viewer, parent):
            candidates = set()
        else:
            candidates, pending = set(), [parent]
            while pending:
                current = pending.pop()
                for child in [member for member, member_parent in UNIT_PARENTS.items() if member_parent == current]:
                    if self.readable(viewer, child) or child in recorded:
                        candidates.add(child)
                    if not self.readable(viewer, child):
                        pending.append(child)

        level = {}
        for unit in candidates:
            units = counted(unit)
            if units:
                level[unit] = (len(units), sum(1 for _, recorded_unit in records if recorded_unit in units), units != {unit})
        return level

    def germplasm_entry(self, viewer: str, name: str) -> GermplasmEntryView | None:
        """
        How the viewer should see a germplasm entry asked for by id (rules 3 and 4): a readable entry with its nearest
        readable sources (or crops) and sinks, through hidden entries only, a direct link keeping its type and one
        through hidden entries UNKNOWN; a hidden crop as a placeholder with its sinks; any other hidden entry bare
        """
        def sources_of(entry: str) -> list[tuple[str, str]]:
            return GERMPLASM[entry][2]

        def sinks_of(entry: str) -> list[tuple[str, str]]:
            return [(sink, source_type) for sink, (_, _, sources) in GERMPLASM.items()
                    for source, source_type in sources if source == entry]

        def is_crop(entry: str) -> bool:
            return not sources_of(entry)

        def nearest(entry: str, step, end) -> dict[str, str]:
            found = {other: source_type for other, source_type in step(entry) if end(other)}
            pending = [other for other, _ in step(entry) if not self.readable(viewer, other)]
            seen = set()
            while pending:
                hidden = pending.pop()
                if hidden in seen:
                    continue
                seen.add(hidden)
                for other, _ in step(hidden):
                    if end(other):
                        found.setdefault(other, 'UNKNOWN')
                    if not self.readable(viewer, other):
                        pending.append(other)
            return found

        readable = self.readable(viewer, name)
        if not readable and not is_crop(name):
            return GermplasmEntryView(readable=False, sources={}, sinks={})
        sinks = nearest(name, sinks_of, lambda other: self.readable(viewer, other))
        sources = nearest(
            name, sources_of, lambda other: self.readable(viewer, other) or is_crop(other)
        ) if readable else {}
        return GermplasmEntryView(readable=readable, sources=sources, sinks=sinks)

    def shown_crops(self, viewer: str) -> set[str]:
        """The crops the viewer can read, and the hidden ones holding entries they can"""
        return {
            name for name, (_, _, sources) in GERMPLASM.items()
            if not sources and (self.readable(viewer, name) or self.germplasm_entry(viewer, name).sinks)
        }

    def shown_programs(self, viewer: str) -> dict[str, dict[str, list[str]]]:
        """
        The programs, trials and studies the viewer should see in a list of programs, by name:
        readable studies, and trials and programs that are readable or hold something shown (rules 4 and 5)
        """
        shown = {}
        for program, trials in PROGRAMS.items():
            shown_trials = {}
            for trial, studies in trials.items():
                shown_studies = [study for study in studies if self.readable(viewer, study)]
                if shown_studies or self.readable(viewer, trial):
                    shown_trials[trial] = shown_studies
            if shown_trials or self.readable(viewer, program):
                shown[program] = shown_trials
        return shown

    def readable_ids(self, viewer: str, *names: str) -> set[int]:
        return {self.ids[name] for name in names if self.readable(viewer, name)}

    def hidden_ids(self, viewer: str, *names: str) -> set[int]:
        return {self.ids[name] for name in names if not self.readable(viewer, name)}


class ReadPolicyScenarioBuilder:
    """
    Builds the scenario through the repositories. File references get their files written to file_storage_path and
    an archival record, as an upload would, when both it and an archival service are given. The viewers' accounts are
    generated, or taken from users (by viewer name) where given, e.g. with known credentials for a test database.
    """

    def __init__(
            self,
            uow_factory: AbstractUnitOfWorkFactory,
            state_store: AbstractStateStore,
            archival_service: AbstractFileArchivalService | None = None,
            file_storage_path: str | Path | None = None,
            users: Dict[str, UserInput] | None = None
    ):
        self.uow_factory = uow_factory
        self.state_store = state_store
        self.archival_service = archival_service
        self.file_storage_path = Path(file_storage_path) if file_storage_path is not None else None
        self.users = users or {}
        self.scenario = ReadPolicyScenario()

    async def _account(self, viewer: str, ontology_role: OntologyRole = OntologyRole.CONTRIBUTOR) -> int:
        if viewer not in self.users:
            return await AccountBuilder(uow_factory=self.uow_factory).account(ontology_role=ontology_role)
        async with self.uow_factory.get_uow() as uow:
            account = await uow.repositories.accounts.create(AccountInput(user=self.users[viewer]))
            await uow.commit()
        return account.user.id

    def _set(self, name: str, entity_id: int, team: str, release: ReadRelease):
        self.scenario.ids[name] = entity_id
        self.scenario.controls[name] = (team, release)

    def _writer_of(self, team: str) -> int:
        return self.scenario['admin' if team == 'root' else 'writer' if team == 'child' else 'stranger']

    def _uow(self, team: str, release: ReadRelease):
        return self.uow_factory.get_uow(
            user_id=self._writer_of(team),
            write_team=self.scenario[team],
            release=release
        )

    async def build(self) -> ReadPolicyScenario:
        await self._teams()
        await self._ontology()
        await self._location_trees()
        await self._layout_trees()
        await self._germplasm()
        await self._units()
        await self._references()
        await self._programs()
        await self._people()
        await self._datasets()
        await self._ontology_commit_and_draft()
        return self.scenario

    async def _teams(self):
        team_trees = TeamTreeBuilder(uow_factory=self.uow_factory)
        s = self.scenario.ids

        s['admin'] = await self._account('admin', ontology_role=OntologyRole.ADMIN)
        s['root'] = await team_trees.team_tree(user_id=s['admin'])
        for access in Access:
            await team_trees.authorise_access(user_id=s['admin'], team_id=s['root'], access=access)

        async with self.uow_factory.get_uow(user_id=s['admin']) as uow:
            team_tree = await uow.repositories.team_trees.get(team_id=s['root'])
            team_tree.add_team(TeamInput(name=TeamTreeBuilder.team_input().name), parent_id=s['root'])
            await uow.commit()
        async with self.uow_factory.get_uow(user_id=s['admin']) as uow:
            team_tree = await uow.repositories.team_trees.get(team_id=s['root'])
            s['child'] = team_tree.get_children_ids(s['root'])[0]
            if config.DATA_PROCESSING_TERMS_VERSION is not None:
                team_tree.declare_legal_entity(
                    agent_id=s['admin'],
                    team_id=s['root'],
                    legal_name=text.new_text(10),
                    privacy_contact=users.new_user_input()['email'],
                    terms_version=config.DATA_PROCESSING_TERMS_VERSION,
                    current_terms_version=config.DATA_PROCESSING_TERMS_VERSION
                )
                await uow.commit()
        for access in (Access.ADMIN, Access.READ):
            await team_trees.authorise_access(user_id=s['admin'], team_id=s['child'], access=access)

        s['writer'] = await self._account('writer')
        for access in (Access.READ, Access.WRITE, Access.CURATE):
            await AuthorisationManager(self.uow_factory).authorise_affiliation(
                agent_id=s['admin'], user_id=s['writer'], team_id=s['child'], access=access
            )

        s['stranger'] = await self._account('stranger')
        s['other'] = await team_trees.team_tree(user_id=s['stranger'])
        for access in Access:
            await team_trees.authorise_access(user_id=s['stranger'], team_id=s['other'], access=access)

        s['outsider'] = await self._account('outsider')

    async def _ontology(self):
        ontology = OntologyBuilder(uow_factory=self.uow_factory)
        admin = self.scenario['admin']
        for types in (
                await ontology.location_types(user_id=admin),
                await ontology.layout_types(user_id=admin),
                await ontology.subject_types(user_id=admin),
                await ontology.record_group_types(user_id=admin),
                await ontology.variable_tree_height(user_id=admin),
                await ontology.variable_canopy_width(user_id=admin),
                await ontology.factor_light_intensity(user_id=admin)
        ):
            self.scenario.ids.update(types)

    async def _ontology_commit_and_draft(self):
        """Last, so no later commit activates the draft"""
        s = self.scenario.ids
        async with self.uow_factory.get_uow(user_id=s['admin']) as uow:
            commit = await uow.ontology.commit_version(
                version_change=VersionChange.MINOR,
                comment="Readpolicy commit with references",
                licence_reference=s['reference_registered'],
                copyright_reference=s['reference_legal_private']
            )
            await uow.commit()
        self.scenario.ids['ontology_commit_version'] = commit.version.packed_version
        async with self.uow_factory.get_uow(user_id=s['admin']) as uow:
            draft = await uow.ontology.create_entry(OntologyBuilder.subject_input(name="Readpolicy draft subject"))
            await uow.commit()
        self.scenario.ids['ontology_subject_draft'] = draft.id

    async def _location_trees(self):
        s = self.scenario.ids
        location_trees = LocationTreeBuilder(self.uow_factory, self.state_store)

        async def root(name: str, team: str, release: ReadRelease):
            async with self._uow(team, release) as uow:
                location_tree = await location_trees.location_tree_from_country(uow)
                await uow.commit()
            self._set(name, location_tree.get_root_id(), team, release)

        async def location(name: str, team: str, release: ReadRelease, parent: str, type_key: str):
            async with self._uow(team, release) as uow:
                location_tree = await uow.repositories.location_trees.get(location_id=s[parent])
                before = set(location_tree._graph.nodes)
                location_tree.add_location(
                    LocationInput(name=text.new_text(10), type=s[type_key]),
                    parent_id=s[parent]
                )
                await uow.commit()
            async with self.uow_factory.get_uow() as uow:
                location_tree = await uow.repositories.location_trees.get(location_id=s[parent])
                (location_id,) = set(location_tree._graph.nodes) - before
            self._set(name, location_id, team, release)

        await root('country', 'root', PUBLIC)
        await location('state', 'child', PRIVATE, 'country', 'ontology_location_state')
        await location('field', 'child', PUBLIC, 'state', 'ontology_location_field')
        await location('centre', 'other', PRIVATE, 'field', 'ontology_location_research_centre')
        await location('lab', 'other', REGISTERED, 'centre', 'ontology_location_lab')
        await location('field_registered', 'child', REGISTERED, 'state', 'ontology_location_field')
        await root('country_private', 'child', PRIVATE)
        await location('state_public', 'child', PUBLIC, 'country_private', 'ontology_location_state')

    async def _layout_trees(self):
        s = self.scenario.ids

        async with self._uow('root', PUBLIC) as uow:
            layout_tree = await uow.repositories.layout_trees.create(LayoutInput(
                name=text.new_text(10),
                type=s['ontology_layout_named'],
                location=s['field'],
                axes=['Chamber']
            ))
            await uow.commit()
        self._set('facility', layout_tree.root.id, 'root', PUBLIC)

        async def layout(name: str, team: str, release: ReadRelease, parent: str, layout_input: LayoutInput, position: list[str]):
            async with self._uow(team, release) as uow:
                layout_tree = await uow.repositories.layout_trees.get(layout_id=s[parent])
                before = set(layout_tree._graph.nodes)
                layout_tree.add_layout(layout_input, parent_id=s[parent], position=position)
                await uow.commit()
            async with self.uow_factory.get_uow() as uow:
                layout_tree = await uow.repositories.layout_trees.get(layout_id=s[parent])
                (layout_id,) = set(layout_tree._graph.nodes) - before
            self._set(name, layout_id, team, release)

        await layout('chamber', 'child', PRIVATE, 'facility', LayoutInput(
            name=text.new_text(10), type=s['ontology_layout_3d'], axes=['Depth', 'Vertical', 'Horizontal']
        ), position=['1'])
        await layout('shelf', 'child', PUBLIC, 'chamber', LayoutInput(
            name=text.new_text(10), type=s['ontology_layout_grid'], axes=['Column', 'Row']
        ), position=['rear', 'top', 'right'])

        async with self._uow('child', PRIVATE) as uow:
            layout_tree = await uow.repositories.layout_trees.create(LayoutInput(
                name=text.new_text(10),
                type=s['ontology_layout_named'],
                location=s['state'],
                axes=['Room']
            ))
            await uow.commit()
        self._set('facility_private', layout_tree.root.id, 'child', PRIVATE)
        await layout('room_public', 'child', PUBLIC, 'facility_private', LayoutInput(
            name=text.new_text(10), type=s['ontology_layout_grid'], axes=['Column', 'Row']
        ), position=['1'])

    async def _units(self):
        s = self.scenario.ids

        async def root(name: str, team: str, release: ReadRelease, location: str):
            async with self._uow(team, release) as uow:
                unit_graph = await uow.repositories.unit_graphs.create(UnitInput(
                    name=text.new_text(10),
                    subject=s['ontology_subject_field'],
                    positions=[Position(location_id=s[location])]
                ))
                await uow.commit()
            self._set(name, unit_graph.root.id, team, release)

        async def unit(
                name: str, team: str, release: ReadRelease, parent: str, subject_key: str,
                location: str | None = None, germplasm: str | None = None
        ):
            async with self._uow(team, release) as uow:
                unit_graph = await uow.repositories.unit_graphs.get(unit_id=s[parent])
                before = set(unit_graph._graph.nodes)
                unit_graph.add_unit(UnitInput(
                    name=text.new_text(10),
                    subject=s[subject_key],
                    germplasm=s[germplasm] if germplasm else None,
                    positions=[Position(location_id=s[location])] if location else []
                ), parents=[s[parent]])
                await uow.commit()
            async with self.uow_factory.get_uow() as uow:
                unit_graph = await uow.repositories.unit_graphs.get(unit_id=s[parent])
                (unit_id,) = set(unit_graph._graph.nodes) - before
            self._set(name, unit_id, team, release)

        await root('field_unit', 'child', PRIVATE, 'field')
        await unit('tree_public', 'child', PUBLIC, 'field_unit', 'ontology_subject_tree', location='state', germplasm='crop_leaf')
        await unit('leaf_private', 'child', PRIVATE, 'tree_public', 'ontology_subject_leaf')
        await unit('rhizosphere_public', 'child', PUBLIC, 'leaf_private', 'ontology_subject_rhizosphere')
        await unit('leaf_other', 'other', PRIVATE, 'tree_public', 'ontology_subject_leaf')
        await unit('rhizosphere_other', 'other', REGISTERED, 'leaf_other', 'ontology_subject_rhizosphere')
        await unit('tree_registered', 'child', REGISTERED, 'field_unit', 'ontology_subject_tree', germplasm='crop_middle')
        await root('plot_public', 'root', PUBLIC, 'field_registered')
        await unit('plant_private', 'child', PRIVATE, 'plot_public', 'ontology_subject_tree')
        await root('plot_private', 'child', PRIVATE, 'field')

    async def _programs(self):
        s = self.scenario.ids

        def study_input():
            return ProgramBuilder.study_input(
                replicate_type=s['ontology_record_group_replicate'],
                batch_type=s['ontology_record_group_batch']
            )

        async def program(name: str, team: str, release: ReadRelease):
            async with self._uow(team, release) as uow:
                stored = await uow.repositories.programs.create(ProgramBuilder.program_input())
                await uow.commit()
            self._set(name, stored.id, team, release)

        async def trial(name: str, team: str, release: ReadRelease, parent: str):
            async with self._uow(team, release) as uow:
                stored = await uow.repositories.programs.get(program_id=s[parent])
                before = set(stored.trials)
                stored.add_trial(TrialInput(name=text.new_text(10)))
                await uow.repositories.programs.update_seen()
                (trial_id,) = set(stored.trials) - before
                await uow.commit()
            self._set(name, trial_id, team, release)

        async def study(name: str, team: str, release: ReadRelease, parent: str):
            async with self._uow(team, release) as uow:
                stored = await uow.repositories.programs.get(trial_id=s[parent])
                before = set(stored.get_trial(s[parent]).studies)
                new_study = study_input()
                new_study.reference_ids = [s[reference] for reference in STUDY_REFERENCES.get(name, [])]
                stored.add_study(trial_id=s[parent], study=new_study)
                await uow.repositories.programs.update_seen()
                (study_id,) = set(stored.get_trial(s[parent]).studies) - before
                await uow.commit()
            self._set(name, study_id, team, release)

        await program('program', 'child', PRIVATE)
        await trial('trial', 'child', PRIVATE, 'program')
        await study('study_public', 'child', PUBLIC, 'trial')
        await study('study_private', 'child', PRIVATE, 'trial')
        await program('program_public', 'root', PUBLIC)
        await trial('trial_public', 'root', PUBLIC, 'program_public')
        await study('study_registered', 'root', REGISTERED, 'trial_public')

    async def _references(self):
        for name, team, release in (
                ('reference_public', 'root', PUBLIC),
                ('reference_private', 'child', PRIVATE),
                ('reference_registered', 'root', REGISTERED),
                ('reference_legal_private', 'child', PRIVATE)
        ):
            reference_type, description = REFERENCES[name]
            if reference_type == 'FILE':
                file_id = uuid.uuid4().hex
                content = f"unit,value\n{name},1\n".encode()
                reference_input = FileReferenceInput(
                    description=description, filename=f"{name}.csv", file_id=file_id, content_type='text/csv'
                )
            else:
                reference_input = LegalReferenceInput(description=description, text=text.new_text(50))
            async with self._uow(team, release) as uow:
                reference = await uow.repositories.references.create(reference_input)
                await uow.commit()
            self._set(name, reference.id, team, release)
            if reference_type == 'FILE':
                self.scenario.files[name] = (file_id, content)
                await self._store_file(file_id, content)

    async def _store_file(self, file_id: str, content: bytes):
        """Write the file and record it for archival, as the upload handler does"""
        if self.file_storage_path is None or self.archival_service is None:
            return
        Path(self.file_storage_path, file_id).write_bytes(content)
        await self.archival_service.create(FileArchivalRecord(
            file_id=file_id,
            file_size=len(content),
            file_hash=hashlib.sha256(content).hexdigest(),
            last_accessed=datetime.now(),
            archive_state=ArchiveState.ARCHIVAL_PENDING,
            local_state=LocalState.LOCAL
        ))

    async def _people(self):
        s = self.scenario.ids
        for name, (team, release, teams, linked_user, claimant) in PEOPLE.items():
            async with self._uow(team, release) as uow:
                person = await uow.repositories.people.create(PersonInput(
                    name=users.new_user_input()['name'],
                    teams=[s[t] for t in teams],
                    informed_attestation=True
                ))
                await uow.commit()
            self._set(name, person.id, team, release)
            if linked_user is not None:
                # a curator of the Person's team links the user, as approving their request would
                async with self.uow_factory.get_uow(user_id=self._writer_of(team)) as uow:
                    stored = await uow.repositories.people.get(person_id=person.id)
                    stored.link(s[linked_user])
                    await uow.commit()
            if claimant is not None:
                async with self.uow_factory.get_uow(user_id=s[claimant]) as uow:
                    stored = await uow.repositories.people.get(person_id=person.id)
                    stored.request_claim(s[claimant])
                    await uow.commit()

    async def _datasets(self):
        s = self.scenario.ids
        for name, (team, release) in (
                ('dataset_public', ('child', PUBLIC)),
                ('dataset_private', ('child', PRIVATE)),
                ('dataset_registered', ('root', REGISTERED))
        ):
            dataset = DATASETS[name]
            async with self._uow(team, release) as uow:
                stored = await uow.repositories.datasets.create(DatasetInput(
                    concept=s['ontology_variable_height'],
                    study=s[dataset['study']],
                    records=[
                        DataRecordInput(unit=s[unit], value=value, reference_ids=[s[r] for r in references] or None)
                        for unit, value, references in dataset['records']
                    ],
                    contributor_ids=[s[person] for person in dataset['contributors']],
                    reference_ids=[s[reference] for reference in dataset['references']]
                ))
                await uow.commit()
            self._set(name, stored.id, team, release)

    async def _germplasm(self):
        s = self.scenario.ids
        for name, (team, release, sources) in GERMPLASM.items():
            async with self._uow(team, release) as uow:
                # names are unique among germplasm, so not left to the random generator
                stored = await uow.germplasm.create_entry(GermplasmInput(
                    name=f"Readpolicy {name.replace('_', ' ')}", description=text.new_text(20)
                ))
                for source, source_type in sources:
                    await uow.germplasm.create_relationship(GermplasmRelationship(
                        source_id=s[source], sink_id=stored.id, source_type=GermplasmSourceType(source_type)
                    ))
                await uow.commit()
            self._set(name, stored.id, team, release)
