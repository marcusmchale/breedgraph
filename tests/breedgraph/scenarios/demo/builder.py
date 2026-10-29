"""
Builds the demonstration database (story.py) through the repositories, each entity written by the account that writes
for its team, as the read-policy scenario is built (read_policy_scenario.py). It repeats the checks the command
handlers make and the repositories don't: record values are parsed against their scales and concepts must be in a
committed version (as handle_dataset_submitted does), contacts are linked and released to registered users, and the
country is public. Without the message bus nothing is emailed, and neither the erasure of a Person nor the deletion of
an account is logged: a real one appends to PERSON_ERASURE_LOG_PATH.
"""
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import bcrypt
from numpy import datetime64

from breedgraph.domain.model.accounts import AccountInput, UserInput
from breedgraph.domain.model.contributions import Contribution
from breedgraph.domain.model.controls import Access, ControlledModelLabel, ReadRelease
from breedgraph.domain.model.datasets import DataRecordInput, DatasetInput, RecordGroup
from breedgraph.domain.model.germplasm import GermplasmInput, GermplasmRelationship
from breedgraph.domain.model.layout_trees import LayoutInput
from breedgraph.domain.model.location_trees import LocationInput
from breedgraph.domain.model.ontology import (
    ConditionInput, ControlMethodInput, DesignInput, FactorInput, LayoutTypeInput, LocationTypeInput,
    ObservationMethodInput, OntologyEntryLabel, RecordGroupTypeInput, ScaleCategory, ScaleInput, SubjectInput,
    TraitInput, VariableInput, VersionChange
)
from breedgraph.domain.model.people import PersonInput
from breedgraph.domain.model.programs import ProgramInput, RecordGroupingInput, StudyInput, TrialInput
from breedgraph.domain.model.references import (
    DataFileInput, DataFormat, FileReferenceInput, LegalReferenceInput, TextFormat, text_hash
)
from breedgraph.domain.model.team_trees import TeamInput
from breedgraph.domain.model.unit_graphs import DerivationStage, Position, UnitDerivation, UnitInput
from breedgraph.service_layer.infrastructure.archival_service import AbstractFileArchivalService
from breedgraph.service_layer.infrastructure.state_store import AbstractStateStore
from breedgraph.service_layer.infrastructure.unit_of_work import AbstractUnitOfWorkFactory

from ..authorisation_manager import AuthorisationManager
from ..location_tree_builder import LocationTreeBuilder
from ..read_policy_scenario import store_file
from ..team_tree_builder import TeamTreeBuilder
from . import values
from .layout import grain_sample_name, plots, selection_plant_name, selection_plot
from .story import (
    ACCOUNTS, COMMITS, CONDITIONS, CONTROL_METHODS, COOPERATIVE_PLOTS, COUNTRY_CODE, DATASETS,
    DESIGNS, FACTORS, FIELD_VARIABLES, GERMPLASM, GRAIN_ARRIVED, GRAIN_VARIABLES, LAB_LAYOUTS, LAYOUT_TYPES,
    LOCATION_TYPES, OBSERVATION_METHODS, ON_VALUE, ORIGINS, PEOPLE, PENDING_REQUESTS, PLACES, PLANS, PROGRAMMES,
    RECORD_GROUP_TYPES, REFERENCES, REGISTERED, SCALES, SEPTORIA_SCALE_CLARIFIED, STUDIES, SUBJECTS, TEAMS, TRAITS,
    TRIALS, VARIABLES, DatasetPlan, Place
)

# File ids are made from the reference's key, so every build stores its files under the same names
FILE_NAMESPACE = uuid.UUID('6f1f8a52-3d7c-4a8e-9a63-5b7e2d4c1a09')
# The account that writes for each team, with it as the write team
WRITERS = {'institute': 'dara', 'breeding': 'bridget', 'field': 'theo', 'lab': 'lena', 'cooperative': 'petra'}
# The viewers whose access the manifest gives: the accounts left, a signed-in account in no team, and anyone
VIEWERS = (*(key for key, account in ACCOUNTS.items() if not account.deleted), 'registered', 'anonymous')
STUDY_TRIALS = {'study_2024': 'lm24', 'study_2025': 'nf25', 'study_lab_2025': 'nf25', 'coop_study': 'coop'}
SITE_METRES_PER_DEGREE = 111_320.0


def file_id(key: str) -> str:
    return uuid.uuid5(FILE_NAMESPACE, key).hex


def coordinates(place: Place) -> list:
    """A place's shape, as latitude and longitude from its site's origin, to 6 decimal places (about 0.1 m)"""
    latitude, longitude = ORIGINS[place.site]
    return [
        {
            'latitude': round(latitude + north / SITE_METRES_PER_DEGREE, 6),
            'longitude': round(longitude + east / (SITE_METRES_PER_DEGREE * math.cos(math.radians(latitude))), 6),
        }
        for east, north in place.shape
    ]


@dataclass
class DemoScenario:
    """What the build wrote, by the story's keys: ids, the controls each entity was written under, and the files"""
    ids: Dict[str, int] = field(default_factory=dict)
    labels: Dict[str, ControlledModelLabel] = field(default_factory=dict)
    controls: Dict[str, Tuple[str, ReadRelease]] = field(default_factory=dict)
    ontology: Dict[str, Dict[str, int]] = field(default_factory=dict)  # by kind, e.g. 'variables', then key
    units: Dict[str, int] = field(default_factory=dict)  # by name
    layouts: Dict[str, int] = field(default_factory=dict)  # by key: a trial's layout and blocks, the lab's layouts
    groupings: Dict[str, Dict[str, int]] = field(default_factory=dict)  # by study key, then name
    files: Dict[str, Tuple[str, bytes, str]] = field(default_factory=dict)  # by reference key: (file id, content, filename)
    commits: List[Tuple[int, str]] = field(default_factory=list)  # (packed version, comment), oldest first
    records: Dict[str, int] = field(default_factory=dict)  # each dataset's record count

    def __getitem__(self, key: str) -> int:
        return self.ids[key]

    def entity(self, key: str, entity_id: int, label: ControlledModelLabel, team: str, release: ReadRelease):
        self.ids[key] = entity_id
        self.labels[key] = label
        self.controls[key] = (team, release)

    def readers(self, team: str) -> set:
        """The viewers with read access to a team's private records: affiliated to it, or heritably to a team above"""
        teams = [team]
        while TEAMS[teams[-1]].parent:
            teams.append(TEAMS[teams[-1]].parent)
        return {
            key for key, account in ACCOUNTS.items() if not account.deleted and any(
                Access.READ in (account.affiliations or {}).get(t, ()) and (t == team or t in account.heritable)
                for t in teams
            )
        }

    def readable(self, viewer: str, key: str) -> bool:
        team, release = self.controls[key]
        if release == ReadRelease.PUBLIC:
            return True
        if release == ReadRelease.REGISTERED:
            return viewer != 'anonymous'
        return viewer in self.readers(team)

    def person_view(self, viewer: str, key: str) -> str | None:
        """FULL, ATTRIBUTION or RESTRICTED (docs/person.md §3); None for visitors, who meet no Persons"""
        if viewer == 'anonymous':
            return None
        team, release = self.controls[key]
        if viewer in self.readers(team) or PEOPLE[key].account == viewer:
            return 'FULL'
        return 'ATTRIBUTION' if release >= ReadRelease.REGISTERED else 'RESTRICTED'


class DemoScenarioBuilder:
    """
    Builds the story into an empty database (apart from the seeded ontology entries) with these passwords for its
    accounts, by key. The files of references are written to file_storage_path, with an archival record, as uploads
    would be, when it and an archival service are given. Accounts are recorded as having consented to the privacy
    notice whose hash is given.
    """

    def __init__(
            self,
            uow_factory: AbstractUnitOfWorkFactory,
            state_store: AbstractStateStore,
            passwords: Dict[str, str],
            archival_service: AbstractFileArchivalService | None = None,
            file_storage_path: str | Path | None = None,
            privacy_notice_hash: str | None = None
    ):
        self.uow_factory = uow_factory
        self.state_store = state_store
        self.passwords = passwords
        self.archival_service = archival_service
        self.file_storage_path = Path(file_storage_path) if file_storage_path is not None else None
        self.privacy_notice_hash = privacy_notice_hash
        self.scenario = DemoScenario()

    async def build(self) -> DemoScenario:
        await self._accounts()
        await self._teams()
        await self._people()
        await self._ontology()
        await self._places()
        await self._layouts()
        for key in GERMPLASM:
            if not GERMPLASM[key].selected_from:
                await self._germplasm(key)
        await self._references()
        await self._programmes()
        await self._trial_units('lm24')
        await self._trial_units('nf25')
        await self._selection_plant()
        await self._grain_samples()
        for key in GERMPLASM:
            if GERMPLASM[key].selected_from:
                await self._germplasm(key)
        await self._trial_units('lm26')
        await self._cooperative_units()
        for key, plan in DATASETS.items():
            await self._dataset(key, plan)
        await self._pending()
        await self._departures()
        return self.scenario

    def _uow(self, team: str, release: ReadRelease):
        """A unit of work of the account that writes for the team, writing under it with this release"""
        s = self.scenario
        return self.uow_factory.get_uow(user_id=s[WRITERS[team]], write_team=s[team], release=release)

    # Accounts and teams ------------------------------------------------------------------------------------------

    async def _accounts(self):
        consented_at = datetime.now(timezone.utc)
        for key, account in ACCOUNTS.items():
            user = UserInput(
                name=key,
                fullname=account.fullname,
                email=account.email,
                password_hash=bcrypt.hashpw(self.passwords[key].encode(), bcrypt.gensalt()).decode(),
                email_verified=True,
                ontology_role=account.ontology_role,
                ontology_role_requested=account.ontology_role_requested,
                privacy_consented_at=consented_at,
                privacy_notice_hash=self.privacy_notice_hash
            )
            async with self.uow_factory.get_uow() as uow:
                stored = await uow.repositories.accounts.create(AccountInput(user=user))
                await uow.commit()
            self.scenario.ids[key] = stored.user.id

    async def _teams(self):
        s = self.scenario
        team_trees = TeamTreeBuilder(uow_factory=self.uow_factory)
        for key, team in TEAMS.items():
            if team.parent is not None:
                continue
            owner = s[team.owner]
            # the creator of a team tree is a heritable admin and reader of it
            async with self.uow_factory.get_uow(user_id=owner) as uow:
                team_tree = await uow.repositories.team_trees.create(TeamInput(name=team.name, attribution=team.attribution))
                await uow.commit()
            s.ids[key] = team_tree.root.id
            children = {child: t for child, t in TEAMS.items() if t.parent == key}
            if children:
                async with self.uow_factory.get_uow(user_id=owner) as uow:
                    team_tree = await uow.repositories.team_trees.get(team_id=s[key])
                    for child in children.values():
                        team_tree.add_team(TeamInput(name=child.name, attribution=child.attribution), parent_id=s[key])
                    await uow.commit()
                async with self.uow_factory.get_uow(user_id=owner) as uow:
                    team_tree = await uow.repositories.team_trees.get(team_id=s[key])
                    by_name = {team_tree.get_team(team_id).name: team_id for team_id in team_tree.get_children_ids(s[key])}
                for child, child_team in children.items():
                    s.ids[child] = by_name[child_team.name]
            # the owner's other accesses: curate as heritably as admin and read, write on the root alone
            for access in TEAMS_OWNER_ACCESS:
                await team_trees.authorise_access(
                    user_id=owner, team_id=s[key], access=access, heritable=access != Access.WRITE
                )

        authorisations = AuthorisationManager(self.uow_factory)
        for key, account in ACCOUNTS.items():
            for team, accesses in (account.affiliations or {}).items():
                if TEAMS[team].owner == key:
                    continue
                admin = s[self._administrator(team)]
                for access in accesses:
                    await authorisations.authorise_affiliation(
                        agent_id=admin, user_id=s[key], team_id=s[team], access=access,
                        heritable=team in account.heritable and access != Access.WRITE
                    )
        for key, account in ACCOUNTS.items():
            async with self.uow_factory.get_uow(user_id=s[key]) as uow:
                stored = await uow.repositories.accounts.get(user_id=s[key])
                stored.user.default_write_team = s[account.write_team]
                await uow.commit()

    @staticmethod
    def _administrator(team: str) -> str:
        """The owner of the team's tree, who administers every team in it"""
        while TEAMS[team].parent is not None:
            team = TEAMS[team].parent
        return TEAMS[team].owner

    async def _people(self):
        s = self.scenario
        for key, person in PEOPLE.items():
            async with self._uow(person.team, person.release) as uow:
                stored = await uow.repositories.people.create(PersonInput(
                    name=person.name,
                    institution=person.institution,
                    teams=[s[team] for team in person.teams],
                    consent_attestation=True
                ))
                await uow.commit()
            s.entity(key, stored.id, ControlledModelLabel.PERSON, person.team, person.release)
            if person.account is not None:
                # linked by a curator of its team, as approving the user's request would
                async with self.uow_factory.get_uow(user_id=s[WRITERS[person.team]]) as uow:
                    stored = await uow.repositories.people.get(person_id=s[key])
                    stored.link(s[person.account])
                    await uow.commit()
                if person.ontology_credit:
                    # which only the linked account chooses
                    async with self.uow_factory.get_uow(user_id=s[person.account]) as uow:
                        stored = await uow.repositories.people.get(person_id=s[key])
                        stored.set_ontology_credit(s[person.account], True)
                        await uow.commit()

    # Ontology ------------------------------------------------------------------------------------------------------

    async def _ontology(self):
        s = self.scenario
        o = s.ontology
        for kind in (
                'location_types', 'layout_types', 'designs', 'record_group_types', 'subjects', 'observation_methods',
                'scales', 'traits', 'variables', 'conditions', 'control_methods', 'factors', 'roles'
        ):
            o[kind] = {}
        # the ontology's licence and copyright, which every version from the second cites; references to be cited by the
        # ontology are public
        for key in ('ontology_licence', 'ontology_copyright'):
            await self._reference(key)

        async with self.uow_factory.get_uow(user_id=s['dara']) as uow:
            ontology = uow.ontology
            o['location_types']['country'] = (
                await ontology.get_entry(name="Country", label=OntologyEntryLabel.LOCATION_TYPE)
            ).id
            for key, (name, parents, description) in LOCATION_TYPES.items():
                entry = await ontology.create_entry(
                    LocationTypeInput(name=name, description=description),
                    parents=[o['location_types'][parent] for parent in parents]
                )
                o['location_types'][key] = entry.id
            for key, (name, axes, description) in LAYOUT_TYPES.items():
                entry = await ontology.create_entry(LayoutTypeInput(name=name, description=description, axes=list(axes)))
                o['layout_types'][key] = entry.id
            for key, (name, synonyms, description) in DESIGNS.items():
                entry = await ontology.create_entry(DesignInput(name=name, synonyms=list(synonyms), description=description))
                o['designs'][key] = entry.id
            for key, (name, extent, description) in RECORD_GROUP_TYPES.items():
                entry = await ontology.create_entry(
                    RecordGroupTypeInput(name=name, description=description, default_extent=extent)
                )
                o['record_group_types'][key] = entry.id
            await self._commit_version(ontology, 0)
            await uow.commit()

        async with self.uow_factory.get_uow(user_id=s['dara']) as uow:
            ontology = uow.ontology
            for key, (name, parents, description) in SUBJECTS.items():
                entry = await ontology.create_entry(
                    SubjectInput(name=name, description=description), parents=[o['subjects'][p] for p in parents]
                )
                o['subjects'][key] = entry.id
            await self._variables(ontology, FIELD_VARIABLES)
            for key, (name, subjects, description) in CONDITIONS.items():
                entry = await ontology.create_condition(
                    ConditionInput(name=name, description=description), subjects=[o['subjects'][x] for x in subjects]
                )
                o['conditions'][key] = entry.id
            for key, (name, control_type, description) in CONTROL_METHODS.items():
                entry = await ontology.create_entry(
                    ControlMethodInput(name=name, description=description, control_type=control_type)
                )
                o['control_methods'][key] = entry.id
            for key, (name, condition, method, scale, description) in FACTORS.items():
                await self._scale(ontology, scale)
                entry = await ontology.create_factor(
                    FactorInput(name=name, description=description), condition_id=o['conditions'][condition],
                    control_method_id=o['control_methods'][method], scale_id=o['scales'][scale]
                )
                o['factors'][key] = entry.id
            await self._commit_version(ontology, 1, cite=True)
            await uow.commit()

        async with self.uow_factory.get_uow(user_id=s['dara']) as uow:
            await self._variables(uow.ontology, GRAIN_VARIABLES)
            await self._commit_version(uow.ontology, 2, cite=True)
            await uow.commit()

        async with self.uow_factory.get_uow(user_id=s['dara']) as uow:
            scale = await uow.ontology.get_entry(entry_id=o['scales']['septoria_scale'])
            scale.description = SEPTORIA_SCALE_CLARIFIED
            await uow.ontology.update_entry(scale)
            await self._commit_version(uow.ontology, 3, cite=True)
            await uow.commit()

        async with self.uow_factory.get_uow(user_id=s['dara']) as uow:
            for role in sorted({role for plan in DATASETS.values() for _, roles in plan.contributions for role in roles} |
                               {role for p in [*PROGRAMMES.values(), *TRIALS.values()]
                                for _, roles in p.contributions for role in roles}):
                o['roles'][role] = (await uow.ontology.get_entry(name=role, label=OntologyEntryLabel.ROLE)).id

    async def _variables(self, ontology, variables: dict):
        o = self.scenario.ontology
        for key, (name, trait, method, scale, description) in variables.items():
            if trait not in o['traits']:
                trait_name, subjects, trait_description = TRAITS[trait]
                entry = await ontology.create_trait(
                    TraitInput(name=trait_name, description=trait_description),
                    subjects=[o['subjects'][subject] for subject in subjects]
                )
                o['traits'][trait] = entry.id
            if method not in o['observation_methods']:
                method_name, observation_type, method_description = OBSERVATION_METHODS[method]
                entry = await ontology.create_entry(ObservationMethodInput(
                    name=method_name, description=method_description, observation_type=observation_type
                ))
                o['observation_methods'][method] = entry.id
            await self._scale(ontology, scale)
            entry = await ontology.create_variable(
                VariableInput(name=name, description=description), trait_id=o['traits'][trait],
                observation_method_id=o['observation_methods'][method], scale_id=o['scales'][scale]
            )
            o['variables'][key] = entry.id

    async def _scale(self, ontology, key: str):
        o = self.scenario.ontology
        if key in o['scales']:
            return
        name, abbreviation, scale_type, description, categories = SCALES[key]
        entry = await ontology.create_scale(ScaleInput(
            name=name, abbreviation=abbreviation, description=description, scale_type=scale_type,
            categories=[ScaleCategory(category, meaning) for category, meaning in categories]
        ))
        o['scales'][key] = entry.id

    async def _commit_version(self, ontology, index: int, cite: bool = False):
        change, comment = COMMITS[index]
        s = self.scenario
        commit = await ontology.commit_version(
            version_change=VersionChange[change],
            comment=comment,
            licence_reference=s['ontology_licence'] if cite else None,
            copyright_reference=s['ontology_copyright'] if cite else None
        )
        s.commits.append((commit.version.packed_version, comment))

    # Places, layouts and germplasm ---------------------------------------------------------------------------------

    async def _places(self):
        s = self.scenario
        o = s.ontology
        country = PLACES['ireland']
        # the handler releases a country publicly; the repository takes the release of the unit of work
        async with self._uow(country.team, ReadRelease.PUBLIC) as uow:
            location_tree = await LocationTreeBuilder(self.uow_factory, self.state_store).location_tree_from_country(
                uow, COUNTRY_CODE
            )
            await uow.commit()
        s.entity('ireland', location_tree.get_root_id(), ControlledModelLabel.LOCATION, country.team, ReadRelease.PUBLIC)

        for key, place in PLACES.items():
            if place.parent is None:
                continue
            async with self._uow(place.team, place.release) as uow:
                location_tree = await uow.repositories.location_trees.get(location_id=s[place.parent])
                existing = set(location_tree.entries)
                location_tree.add_location(LocationInput(
                    name=place.name,
                    type=o['location_types'][place.type],
                    description=place.description,
                    code=place.code,
                    address=place.address,
                    coordinates=coordinates(place)
                ), parent_id=s[place.parent])
                await uow.repositories.location_trees.update_seen()
                [location_id] = set(location_tree.entries) - existing
                await uow.commit()
            s.entity(key, location_id, ControlledModelLabel.LOCATION, place.team, place.release)

    async def _layouts(self):
        s = self.scenario
        layout_types = s.ontology['layout_types']
        for key, plan in PLANS.items():
            async with self._uow('field', plan.release) as uow:
                layout_tree = await uow.repositories.layout_trees.create(LayoutInput(
                    name=plan.layout, type=layout_types['trial_blocks'], location=s[plan.field], axes=['Block']
                ))
                root_id = layout_tree.get_root_id()
                for block in range(1, plan.blocks + 1):
                    layout_tree.add_layout(
                        LayoutInput(name=f"Block {block}", type=layout_types['plot_grid'], axes=['Row', 'Column']),
                        parent_id=root_id, position=[str(block)]
                    )
                await uow.commit()
            async with self.uow_factory.get_uow() as uow:
                layout_tree = await uow.repositories.layout_trees.get(layout_id=root_id)
                by_name = {layout.name: layout.id for layout in layout_tree.entries.values()}
            s.entity(f"layout_{key}", root_id, ControlledModelLabel.LAYOUT, 'field', plan.release)
            s.layouts[key] = root_id
            for block in range(1, plan.blocks + 1):
                s.layouts[f"{key}_block_{block}"] = by_name[f"Block {block}"]

        for key, (name, type_key, location, axes, team, release) in LAB_LAYOUTS.items():
            async with self._uow(team, release) as uow:
                layout_tree = await uow.repositories.layout_trees.create(LayoutInput(
                    name=name, type=layout_types[type_key], location=s[location], axes=list(axes)
                ))
                await uow.commit()
            s.entity(f"layout_{key}", layout_tree.get_root_id(), ControlledModelLabel.LAYOUT, team, release)
            s.layouts[key] = layout_tree.get_root_id()

    async def _germplasm(self, key: str):
        s = self.scenario
        variety = GERMPLASM[key]
        async with self._uow('breeding', variety.release) as uow:
            stored = await uow.germplasm.create_entry(GermplasmInput(
                name=variety.name,
                description=variety.description,
                synonyms=list(variety.synonyms),
                origin=s[variety.origin] if variety.origin else None,
                time=datetime64(variety.time) if variety.time else None,
                unit=s.units[selection_plant_name()] if variety.selected_from else None,
                reproduction=variety.reproduction,
                control_methods=[s.ontology['control_methods'][method] for method in variety.control_methods]
            ))
            for source, source_type in variety.sources:
                await uow.germplasm.create_relationship(GermplasmRelationship(
                    source_id=s[source], sink_id=stored.id, source_type=source_type
                ))
            await uow.commit()
        s.entity(key, stored.id, ControlledModelLabel.GERMPLASM, 'breeding', variety.release)

    # References and programmes -------------------------------------------------------------------------------------

    async def _references(self):
        for key in REFERENCES:
            if key not in self.scenario.ids:
                await self._reference(key)

    async def _reference(self, key: str):
        kind, description, team, release, filename = REFERENCES[key]
        content = None
        if kind == 'legal':
            text = values.ONTOLOGY_LICENCE if key == 'ontology_licence' else values.ONTOLOGY_COPYRIGHT
            reference_input = LegalReferenceInput(description=description, text=text, content_hash=text_hash(text))
        elif kind == 'legal_markdown':
            reference_input = LegalReferenceInput(
                description=description, text=values.OPEN_LICENCE, text_format=TextFormat.MARKDOWN,
                content_hash=text_hash(values.OPEN_LICENCE)
            )
        elif kind == 'file_pdf':
            content = values.field_plan_pdf('lm24' if key == 'plan_2024' else 'nf25')
            reference_input = FileReferenceInput(
                description=description, filename=filename, file_id=file_id(key), content_type='application/pdf'
            )
        else:
            raise ValueError(f"Unknown kind of reference {kind}")
        async with self._uow(team, release) as uow:
            reference = await uow.repositories.references.create(reference_input)
            await uow.commit()
        self.scenario.entity(key, reference.id, ControlledModelLabel.REFERENCE, team, release)
        if content is not None:
            await self._store(key, file_id(key), content, filename)

    async def _store(self, key: str, stored_file_id: str, content: bytes, filename: str):
        self.scenario.files[key] = (stored_file_id, content, filename)
        await store_file(self.file_storage_path, self.archival_service, stored_file_id, content)

    def _contributions(self, credits) -> List[Contribution]:
        roles = self.scenario.ontology['roles']
        return [
            Contribution(person=self.scenario[person], roles=[roles[role] for role in person_roles])
            for person, person_roles in credits
        ]

    def _contacts(self, contacts) -> List[int]:
        # as the programs handler requires (_verify_contacts): linked to an account, and released to registered users
        for person in contacts:
            if PEOPLE[person].account is None or PEOPLE[person].release < REGISTERED:
                raise ValueError(f"A contact must be linked and released to registered users: {person}")
        return [self.scenario[person] for person in contacts]

    async def _programmes(self):
        s = self.scenario
        for key, programme in PROGRAMMES.items():
            async with self._uow(programme.team, programme.release) as uow:
                stored = await uow.repositories.programs.create(ProgramInput(
                    name=programme.name,
                    description=programme.description,
                    contact_ids=self._contacts(programme.contacts),
                    contributions=self._contributions(programme.contributions)
                ))
                await uow.commit()
            s.entity(key, stored.id, ControlledModelLabel.PROGRAM, programme.team, programme.release)

        for key, trial in TRIALS.items():
            team = PROGRAMMES[trial.programme].team
            async with self._uow(team, trial.release) as uow:
                stored = await uow.repositories.programs.get(program_id=s[trial.programme])
                stored.add_trial(TrialInput(
                    name=trial.name,
                    description=trial.description,
                    start=datetime64(trial.start),
                    end=datetime64(trial.end),
                    contact_ids=self._contacts(trial.contacts),
                    contributions=self._contributions(trial.contributions)
                ))
                await uow.repositories.programs.update_seen()
                trial_id = next(t.id for t in stored.trials.values() if t.name == trial.name)
                await uow.commit()
            s.entity(key, trial_id, ControlledModelLabel.TRIAL, team, trial.release)

        o = s.ontology
        for key, study in STUDIES.items():
            team = PROGRAMMES[TRIALS[study.trial].programme].team
            async with self._uow(team, study.release) as uow:
                stored = await uow.repositories.programs.get(trial_id=s[study.trial])
                stored.add_study(trial_id=s[study.trial], study=StudyInput(
                    name=study.name,
                    description=study.description,
                    practices=study.practices,
                    start=datetime64(study.start),
                    end=datetime64(study.end),
                    design_id=o['designs'][study.design] if study.design else None,
                    licence_id=s[study.licence] if study.licence else None,
                    reference_ids=[s[reference] for reference in study.references],
                    groupings=[
                        RecordGroupingInput(
                            type=o['record_group_types'][grouping.type], name=grouping.name, scope=grouping.scope,
                            extent=grouping.extent
                        )
                        for grouping in study.groupings
                    ]
                ))
                await uow.repositories.programs.update_seen()
                stored_study = next(
                    st for st in stored.get_trial(s[study.trial]).studies.values() if st.name == study.name
                )
                s.groupings[key] = {grouping.name: grouping.id for grouping in stored_study.groupings}
                await uow.commit()
            s.entity(key, stored_study.id, ControlledModelLabel.STUDY, team, study.release)

    # Units ---------------------------------------------------------------------------------------------------------

    async def _trial_units(self, trial: str):
        """A trial's area of its field as the root of a unit graph, with its plots, each placed in its block"""
        s = self.scenario
        plan = PLANS[trial]
        subjects = s.ontology['subjects']
        sown = datetime64(plan.sown)
        harvested = datetime64(plan.harvested) if plan.harvested else None
        async with self._uow('field', plan.release) as uow:
            unit_graph = await uow.repositories.unit_graphs.create(UnitInput(
                name=plan.area,
                subject=subjects['field'],
                description=f"The plots of the {plan.layout} in {PLACES[plan.field].name}",
                positions=[Position(location_id=s[plan.field], start=sown, end=harvested)]
            ))
            root_id = unit_graph.get_root_id()
            for plot in plots(trial):
                derived_from = []
                if GERMPLASM[plot.entry].selected_from:
                    derived_from = [UnitDerivation(
                        unit_id=s.units[selection_plant_name()], stage=DerivationStage.SEED,
                        description="Sown from the seed of the selected plant"
                    )]
                unit_graph.add_unit(UnitInput(
                    name=plot.name,
                    subject=subjects['plot'],
                    germplasm=s[plot.entry],
                    positions=[Position(
                        location_id=s[plan.field],
                        layout_id=s.layouts[f"{trial}_block_{plot.block}"],
                        coordinates=[plot.row, plot.column],
                        start=sown,
                        end=harvested
                    )],
                    derived_from=derived_from
                ), parents=[root_id])
            await uow.commit()
        await self._read_units(root_id, 'field', plan.release)

    async def _read_units(self, unit_id: int, team: str, release: ReadRelease, names: set | None = None):
        s = self.scenario
        async with self.uow_factory.get_uow() as uow:
            unit_graph = await uow.repositories.unit_graphs.get(unit_id=unit_id)
            for unit in unit_graph.entries.values():
                if unit.name in s.units or (names is not None and unit.name not in names):
                    continue
                s.units[unit.name] = unit.id
                s.entity(f"unit:{unit.name}", unit.id, ControlledModelLabel.UNIT, team, release)

    async def _selection_plant(self):
        """The 2025 plant the selection EPB 25-S03 was made from, below its plot, whose position it shares"""
        s = self.scenario
        plot = selection_plot()
        release = PLANS['nf25'].release
        async with self._uow('field', release) as uow:
            unit_graph = await uow.repositories.unit_graphs.get(unit_id=s.units[plot.name])
            unit_graph.add_unit(UnitInput(
                name=selection_plant_name(), subject=s.ontology['subjects']['plant'],
                description="Selected for its clean leaves on 2025-07-15; its seed was kept apart"
            ), parents=[s.units[plot.name]])
            await uow.commit()
        await self._read_units(s.units[plot.name], 'field', release, names={selection_plant_name()})

    async def _grain_samples(self):
        """The grain of every 2025 plot, which reached the laboratory together: one arrival"""
        s = self.scenario
        arrived = datetime64(GRAIN_ARRIVED)
        async with self._uow('lab', ReadRelease.PRIVATE) as uow:
            unit_graph = await uow.repositories.unit_graphs.get(unit_id=s.units[PLANS['nf25'].area])
            for plot in plots('nf25'):
                unit_graph.add_unit(UnitInput(
                    name=grain_sample_name(plot.name),
                    subject=s.ontology['subjects']['grain_sample'],
                    positions=[Position(location_id=s['laboratory'], start=arrived)]
                ), parents=[s.units[plot.name]])
            await uow.commit()
        await self._read_units(
            s.units[PLANS['nf25'].area], 'lab', ReadRelease.PRIVATE,
            names={grain_sample_name(plot.name) for plot in plots('nf25')}
        )

    async def _cooperative_units(self):
        s = self.scenario
        name, sown, harvested = COOPERATIVE_PLOTS['area']
        position = Position(location_id=s['seed_field'], start=datetime64(sown), end=datetime64(harvested))
        async with self._uow('cooperative', ReadRelease.PRIVATE) as uow:
            unit_graph = await uow.repositories.unit_graphs.create(UnitInput(
                name=name, subject=s.ontology['subjects']['field'], positions=[position]
            ))
            root_id = unit_graph.get_root_id()
            for plot_name in COOPERATIVE_PLOTS['plots']:
                unit_graph.add_unit(UnitInput(
                    name=plot_name, subject=s.ontology['subjects']['plot'], germplasm=s[COOPERATIVE_PLOTS['entry']],
                    positions=[position]
                ), parents=[root_id])
            await uow.commit()
        await self._read_units(root_id, 'cooperative', ReadRelease.PRIVATE)

    # Datasets ------------------------------------------------------------------------------------------------------

    def _concept(self, key: str) -> int:
        o = self.scenario.ontology
        return o['variables'][key] if key in VARIABLES else o['factors'][key]

    async def _nir_files(self, plan: DatasetPlan) -> Dict[str, int]:
        """
        The spectra the NIR records cite, as data file references, stored before the dataset: the archival record of
        a file is written in a transaction of its own, which would wait on a reference not yet committed
        """
        s = self.scenario
        references = {}
        async with self._uow('lab', plan.release) as uow:
            for plot in values.nir_plots(block=1):
                reference_key = f"nir_{plot.name}"
                reference = await uow.repositories.references.create(DataFileInput(
                    description=f"NIR spectrum of {grain_sample_name(plot.name)}",
                    filename=values.nir_filename(plot),
                    file_id=file_id(reference_key),
                    content_type='text/csv',
                    format=DataFormat.CSV
                ))
                references[plot.name] = reference.id
                s.entity(reference_key, reference.id, ControlledModelLabel.REFERENCE, 'lab', plan.release)
            await uow.commit()
        for plot in values.nir_plots(block=1):
            reference_key = f"nir_{plot.name}"
            await self._store(reference_key, file_id(reference_key), values.nir_spectrum(plot), values.nir_filename(plot))
        return references

    def _records(self, key: str, plan: DatasetPlan, references: Dict[str, int]) -> List[DataRecordInput]:
        s = self.scenario
        groupings = s.groupings.get(plan.study, {})

        def start(value: str):
            if plan.on is None:
                return None
            return datetime64(value if plan.on == ON_VALUE else plan.on)

        if plan.units == 'plots':
            trial = STUDY_TRIALS[plan.study]
            return [
                DataRecordInput(unit=s.units[name], value=value, start=start(value))
                for name, value in values.plot_values(trial, plan.concept)
            ]
        if plan.units == 'area':
            name, value = values.area_value(STUDY_TRIALS[plan.study], plan.concept)
            return [DataRecordInput(unit=s.units[name], value=value, start=start(value))]
        if plan.units == 'coop_plots':
            return [
                DataRecordInput(unit=s.units[name], value=value, start=start(value))
                for name, value in values.cooperative_yields()
            ]
        if plan.units == 'samples' and plan.concept == 'grain_weight':
            return [
                DataRecordInput(
                    unit=s.units[grain_sample_name(plot.name)], value=weight, start=start(weight),
                    groups=[RecordGroup(id=groupings["Grain count"], code=str(count))]
                )
                for plot in plots('nf25') for count, weight in enumerate(values.grain_weights(plot), start=1)
            ]
        if plan.units == 'samples' and plan.concept == 'protein':
            return [
                DataRecordInput(
                    unit=s.units[grain_sample_name(plot.name)], value=values.protein(plot),
                    start=start(values.protein(plot)),
                    groups=[RecordGroup(id=groupings["NIR run"], code=values.nir_batch(plot))]
                )
                for plot in plots('nf25')
            ]
        if plan.units == 'nir_samples':
            return [
                DataRecordInput(
                    unit=s.units[grain_sample_name(plot.name)], start=datetime64(plan.on),
                    references=[references[plot.name]],
                    groups=[RecordGroup(id=groupings["NIR run"], code=values.nir_batch(plot))]
                )
                for plot in values.nir_plots(block=1)
            ]
        raise ValueError(f"Unknown units {plan.units} of dataset {key}")

    async def _dataset(self, key: str, plan: DatasetPlan):
        """As the submission handler creates one: its records parsed against the concept's scale, then stored with it"""
        s = self.scenario
        team = ACCOUNTS[plan.writer].write_team
        concept = self._concept(plan.concept)
        references = await self._nir_files(plan) if plan.units == 'nir_samples' else {}
        records = self._records(key, plan, references)
        async with self.uow_factory.get_uow(user_id=s[plan.writer], write_team=s[team], release=plan.release) as uow:
            await uow.ontology.require_entries([concept])
            dataset_input = DatasetInput(
                concept=concept, study=s[plan.study], contributions=self._contributions(plan.contributions)
            )
            program = await uow.repositories.programs.get(study_id=s[plan.study])
            study = program.get_study(s[plan.study])
            scale = await uow.ontology.get_concept_scale(concept)
            errors = [
                f"record {index}: {error}"
                for index, error in enumerate(
                    dataset_input.add_records(records, scale, study.get_grouping_ids())
                )
                if error is not None
            ]
            if errors:
                raise ValueError(f"Dataset {key} has records that don't parse: {errors[:5]}")
            dataset = await uow.repositories.datasets.create(dataset_input)
            await uow.commit()
        s.entity(key, dataset.id, ControlledModelLabel.DATASET, team, plan.release)
        s.records[key] = len(records)

    # Pending requests and departures -------------------------------------------------------------------------------

    async def _pending(self):
        s = self.scenario
        for key, person in PEOPLE.items():
            if person.claimant is None:
                continue
            async with self.uow_factory.get_uow(user_id=s[person.claimant]) as uow:
                stored = await uow.repositories.people.get(person_id=s[key])
                stored.request_claim(s[person.claimant])
                await uow.commit()
        for account, team, access in PENDING_REQUESTS:
            async with self.uow_factory.get_uow(user_id=s[account]) as uow:
                team_tree = await uow.repositories.team_trees.get(team_id=s[team])
                team_tree.request_affiliation(agent_id=s[account], team_id=s[team], access=access, user_id=s[account])
                await uow.commit()

    async def _departures(self):
        s = self.scenario
        for key, account in ACCOUNTS.items():
            if not account.deleted:
                continue
            # as delete_account does, keeping the Person: unlinked first, as the people repository authorises by the
            # stored link
            async with self.uow_factory.get_uow(user_id=s[key]) as uow:
                stored = await uow.repositories.accounts.get(user_id=s[key])
                person = await uow.repositories.people.get(user_id=s[key])
                if person is not None:
                    controller = await uow.controls.get_controller(person.label, person.id)
                    person.unlink(s[key], controller, uow.controls.access_teams[Access.ADMIN])
                    await uow.repositories.people.update_seen()
                stored.delete()
                await uow.repositories.accounts.remove(stored)
                await uow.commit()
        for key, person in PEOPLE.items():
            if not person.erased:
                continue
            # by an admin of its team; the erasure log is written only by the event, which this build doesn't publish
            admin = s[self._administrator(person.team)]
            async with self.uow_factory.get_uow(user_id=admin) as uow:
                stored = await uow.repositories.people.get(person_id=s[key])
                controller = await uow.controls.get_controller(stored.label, stored.id)
                stored.erase(agent_id=admin, controller=controller, admin_teams=uow.controls.access_teams[Access.ADMIN])
                await uow.commit()


# The accesses a team tree's owner gives themselves besides the admin and read access its creation gives: curate,
# heritably, and write on the root alone (write can't be heritable)
TEAMS_OWNER_ACCESS = (Access.CURATE, Access.WRITE)
