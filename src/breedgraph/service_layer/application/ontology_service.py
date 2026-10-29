from breedgraph.custom_exceptions import (
    RelationshipExistsError, IdentityExistsError, UnauthorisedOperationError, IllegalOperationError, NoResultFoundError
)

from breedgraph.domain.model.ontology import (
    OntologyEntryInput, OntologyEntryStored,
    TermInput, TermStored,
    SubjectInput, SubjectStored,
    TraitInput, TraitStored,
    ObservationMethodInput, ObservationMethodStored,
    ScaleBase, ScaleInput, ScaleStored,
    VariableInput, VariableStored,
    ConditionInput, ConditionStored,
    FactorInput, FactorStored,
    ControlMethodInput, ControlMethodStored,
    EventTypeInput, EventTypeStored,
    LocationTypeInput, LocationTypeStored,
    DesignInput, DesignStored,
    RoleInput, RoleStored,
    LayoutTypeInput, LayoutTypeStored,
    OntologyEntryLabel, LifecyclePhase, VersionChange, Version, OntologyCommit,
    OntologyRelationshipBase, ParentRelationship, TermRelationship, SubjectRelationship,
    FactorComponentRelationship, VariableComponentRelationship,
    EventTypeComponentRelationship, EntryLifecycle, RelationshipLifecycle,
    OntologyRelationshipLabel, ScaleType,
    RecordGroupTypeInput, RecordGroupTypeStored
)

from breedgraph.domain.model.accounts import OntologyRole
from breedgraph.domain.model.controls import ControlledModelLabel, ReadRelease
from breedgraph.domain.events import Event
from breedgraph.domain.events.ontology import OntologyVersionCreated

from breedgraph.service_layer.persistence import OntologyPersistenceService
from breedgraph.service_layer.queries.read_models import (
    OntologyEntryOutput, ScaleOutput, VariableOutput, FactorOutput
)
from breedgraph.service_layer.application.access_control import AbstractAccessControlService

from breedgraph.service_layer.mappers import ontology_mapper
from breedgraph.domain.services.ontology_lifecycles import (
    deprecate_with_entries, cancel_with_entries, restore_with_entries, is_current
)

from typing import Set, List, Tuple, Dict, Any, AsyncGenerator, overload, Literal, TypeVar

import logging

logger = logging.getLogger(__name__)

T = TypeVar("T", SubjectStored, TraitStored, ScaleStored)  # expand as needed

class OntologyApplicationService:
    """
    Unified application service for all ontology mutation operations.
    Handles validation, state management, persistence, and event publishing.

    Projections that depend on version and view should be provided in views
    Constraints should be enforced only for the current version.
    """
    def __init__(
            self,
            persistence_service: OntologyPersistenceService,
            user_id: int|None = None,
            role: OntologyRole|None = None,
            access_control_service: AbstractAccessControlService|None = None
    ):
        self.persistence = persistence_service
        self.user_id = user_id
        self.role = role
        # references are controlled: citing one needs read access to it (docs/read-access.md, rule 10)
        self.access_control = access_control_service
        self.events: List[Event] = []
        # in memory store for lifecycle management
        self._entry_lifecycles: Dict[int, EntryLifecycle] = {}
        self._relationship_lifecycles: Dict[int, RelationshipLifecycle] = {}
        # versions of each lifecycle as last loaded or saved, so only lifecycles that changed are saved
        self._stored_entry_versions: Dict[int, Dict[str, int]] = {}
        self._stored_relationship_versions: Dict[int, Dict[str, int]] = {}

    def collect_events(self):
        while self.events:
            yield self.events.pop(0)

    async def lock_entries(self, entry_ids: List[int], locked: bool = True) -> None:
        """Lock or unlock entries, so they stay stable (docs/contributions.md §4); for ontology admins"""
        if not self.role == OntologyRole.ADMIN:
            raise UnauthorisedOperationError("Only ontology admins can lock or unlock entries")
        await self._validate_entries_exist(entry_ids)
        await self.persistence.set_entries_locked(list(entry_ids), locked, self.user_id)

    async def get_seeded_entry(self, seed_key: str) -> OntologyEntryStored | None:
        """An entry seeded with this key (ontology_seed.py), found whatever its name"""
        entry_id = await self.persistence.get_entry_id_by_seed_key(seed_key)
        return await self.persistence.get_entry(entry_id=entry_id) if entry_id is not None else None

    async def seed_entry(self, entry: OntologyEntryInput, seed_key: str) -> OntologyEntryStored:
        """Create an entry every deployment starts with, locked and keyed so code can find it whatever its name"""
        created = await self.create_entry(entry)
        await self.persistence.set_seed_key(created.id, seed_key)
        await self.lock_entries([created.id])
        return created

    async def _require_unlocked(self, entry_ids) -> None:
        for entry_id in set(entry_ids):
            entry = await self.persistence.get_entry(entry_id=entry_id)
            if entry is not None and entry.locked:
                raise UnauthorisedOperationError(f"{entry.label.value} {entry.name} is locked")

    async def _require_unlocked_sources(self, relationships: List[OntologyRelationshipBase]) -> None:
        """
        A locked entry keeps the relationships that define it: those from it, other than to its children and terms.
        Relationships to it from other entries stay open.
        """
        await self._require_unlocked([
            relationship.source_id for relationship in relationships if relationship.label.defines_source
        ])

    async def _require_citable_references(self, reference_ids) -> None:
        """
        You can only cite what you can read, a reference the user cannot read being reported as not found; and the
        ontology is shared, so what it cites, an entry's references or a version's licence and copyright, is public,
        and stays so: the release floor counts the ontology as public (docs/read-access.md, rule 10)
        """
        reference_ids = [reference_id for reference_id in reference_ids or [] if reference_id is not None]
        if not reference_ids:
            return
        if self.access_control is None:
            raise UnauthorisedOperationError("Citing references requires access control")
        await self.access_control.require_read(ControlledModelLabel.REFERENCE, reference_ids)
        controllers = await self.access_control.get_controllers(ControlledModelLabel.REFERENCE, reference_ids)
        for reference_id in reference_ids:
            release = controllers[reference_id].release
            if release != ReadRelease.PUBLIC:
                raise IllegalOperationError(
                    f"Reference {reference_id} is released as {release.name}: the ontology is shared, so it cites "
                    f"public references only"
                )

    async def get_current_version(self):
        return await self.persistence.get_current_version()

    async def commit_version(
            self,
            version_change: VersionChange = VersionChange.PATCH,
            comment: str|None = None,
            licence_reference: int|None = None,
            copyright_reference: int|None = None
    ) -> OntologyCommit:
        """
        Create a new ontology version with commit metadata. A version keeps the latest one's licence unless it names
        another, and takes the standard CC BY 4.0 where the latest has none, so the ontology always has a licence:
        CC BY 4.0, as seeding gives the first version, unless an ontology admin names another (docs/licences.md §6).
        """
        if not self.role in [OntologyRole.EDITOR, OntologyRole.ADMIN]:
            raise UnauthorisedOperationError("Only admins and editors can commit versions")
        elif not self.user_id:
            raise UnauthorisedOperationError("Only registered users can commit versions")
        if licence_reference is None:
            licence_reference = await self.persistence.get_default_licence()
        await self._require_citable_references([licence_reference, copyright_reference])

        commit = await self.persistence.commit_version(
            user_id = self.user_id,
            version_change=version_change,
            comment=comment,
            licence_reference=licence_reference,
            copyright_reference=copyright_reference
        )
        await self.activate_drafts(commit.version)
        await self.remove_deprecated(commit.version)
        # Add event for version creation (e.g. to contact ontology curators etc.)
        self.events.append(OntologyVersionCreated(version_id=commit.version.id))
        return commit

    async def activate_drafts(self, version: Version):
        """Set all drafts to activated at the corresponding version."""
        if not self.user_id:
            raise UnauthorisedOperationError("User ID required")
        await self.persistence.activate_drafts(version, self.user_id)

    async def remove_deprecated(self, version: Version):
        if not self.user_id:
            raise UnauthorisedOperationError("User ID required")
        """Remove all deprecated entries at the corresponding version."""
        await self.persistence.remove_deprecated(version, self.user_id)

    async def activate_entries(self, entry_ids):
        if not self.role in [OntologyRole.EDITOR, OntologyRole.ADMIN]:
            raise UnauthorisedOperationError("Only admins and editors can activate entries")
        await self._load_entry_lifecycles(entry_ids)
        current_version = await self.get_current_version()
        for entry_id in entry_ids:
            lifecycle = await self._get_entry_lifecycle(entry_id)
            if not lifecycle.current_phase==LifecyclePhase.ACTIVE:
                lifecycle.set_version_activated(current_version)
        await self._save_entry_lifecycles()

    async def deprecate_entries(self, entry_ids):
        """Deprecates the entries with their relationships (domain/services/ontology_lifecycles.py)"""
        if not self.role in [OntologyRole.EDITOR, OntologyRole.ADMIN]:
            raise UnauthorisedOperationError("Only admins and editors can deprecate entries")
        await self._require_unlocked(entry_ids)

        await self._load_entry_lifecycles(entry_ids)
        relationships = await self._load_relationships_of(entry_ids)
        current_version = await self.get_current_version()
        deprecate_with_entries(
            entry_ids, relationships, self._relationship_lifecycles, self._entry_lifecycles, current_version
        )
        for entry_id in entry_ids:
            lifecycle = await self._get_entry_lifecycle(entry_id)
            if not lifecycle.current_phase==LifecyclePhase.DEPRECATED:
                lifecycle.set_version_deprecated(current_version)
        await self._save_entry_lifecycles()
        await self._save_relationship_lifecycles()

    async def cancel_deprecate_entries(self, entry_ids):
        """Brings back the relationships deprecated with the entries (domain/services/ontology_lifecycles.py)"""
        if not self.role in [OntologyRole.EDITOR, OntologyRole.ADMIN]:
            raise UnauthorisedOperationError("Only admins and editors can cancel deprecate entries")

        await self._load_entry_lifecycles(entry_ids)
        relationships = await self._load_relationships_of(entry_ids)
        cancel_with_entries(entry_ids, relationships, self._relationship_lifecycles)
        for entry_id in entry_ids:
            lifecycle = await self._get_entry_lifecycle(entry_id)
            lifecycle.cancel_deprecation()
        await self._save_entry_lifecycles()
        await self._save_relationship_lifecycles()

    async def restore_entries(self, entry_ids):
        """
        Brings removed entries back as drafts, which the next commit activates, with the relationships removed with them
        (domain/services/ontology_lifecycles.py). Each keeps its id, so data that cites it and new data cite the same entry.
        """
        if not self.role in [OntologyRole.EDITOR, OntologyRole.ADMIN]:
            raise UnauthorisedOperationError("Only admins and editors can restore entries")
        entry_ids = list(dict.fromkeys(entry_ids))
        await self._load_entry_lifecycles(entry_ids)
        for entry_id in entry_ids:
            if (await self._get_entry_lifecycle(entry_id)).current_phase is not LifecyclePhase.REMOVED:
                raise IllegalOperationError(
                    f"Entry {entry_id} is not removed: only removed entries are restored, a deprecation is cancelled"
                )
        for entry in await self.persistence.get_cited_entries(entry_ids):
            if await self.persistence.name_in_use(entry.label, entry.name, entry.id):
                raise IdentityExistsError(
                    f"Another {entry.label.value} is using the name {entry.name}, so {entry.label.value} {entry.id} can't be restored"
                )
            if entry.abbreviation and await self.persistence.abbreviation_in_use(entry.label, entry.abbreviation, entry.id):
                raise IdentityExistsError(
                    f"Another {entry.label.value} is using the abbreviation {entry.abbreviation}, "
                    f"so {entry.label.value} {entry.id} can't be restored"
                )
        relationships = await self._load_relationships_of(entry_ids, removed=True)
        current_version = await self.get_current_version()
        restore_with_entries(
            entry_ids, relationships, self._relationship_lifecycles, self._entry_lifecycles, current_version
        )
        for entry_id in entry_ids:
            (await self._get_entry_lifecycle(entry_id)).set_version_drafted(current_version)
        await self._save_entry_lifecycles()
        await self._save_relationship_lifecycles()

    async def _load_relationships_of(self, entry_ids, removed: bool = False) -> List[OntologyRelationshipBase]:
        """
        The relationships of the entries, removed ones too if asked, with their lifecycles and those of their ends
        """
        phases = [LifecyclePhase.DRAFT, LifecyclePhase.ACTIVE, LifecyclePhase.DEPRECATED]
        if removed:
            phases.append(LifecyclePhase.REMOVED)
        relationships = [
            relationship async for relationship in self.persistence.get_relationships(entry_ids=list(entry_ids), phases=phases)
        ]
        await self._load_relationship_lifecycles([relationship.id for relationship in relationships])
        ends = {entry_id for relationship in relationships for entry_id in (relationship.source_id, relationship.target_id)}
        await self._load_entry_lifecycles(list(ends - set(self._entry_lifecycles)))
        return relationships

    async def activate_relationships(self, relationship_ids):
        if not self.role in [OntologyRole.EDITOR, OntologyRole.ADMIN]:
            raise UnauthorisedOperationError("Only admins and editors can activate relationships")
        await self._load_relationship_lifecycles(relationship_ids)
        current_version = await self.get_current_version()
        for relationship_id in relationship_ids:
            lifecycle = await self._get_relationship_lifecycle(relationship_id)
            if not lifecycle.current_phase==LifecyclePhase.ACTIVE:
                lifecycle.set_version_activated(current_version)
        await self._save_relationship_lifecycles()

    async def deprecate_relationships(self, relationship_ids):
        if not self.role in [OntologyRole.EDITOR, OntologyRole.ADMIN]:
            raise UnauthorisedOperationError("Only admins and editors can deprecate relationships")
        await self._load_relationship_lifecycles(relationship_ids)
        current_version = await self.get_current_version()
        for relationship_id in relationship_ids:
            lifecycle = await self._get_relationship_lifecycle(relationship_id)
            if not lifecycle.current_phase==LifecyclePhase.DEPRECATED:
                lifecycle.set_version_deprecated(current_version)
        await self._save_relationship_lifecycles()

    async def cancel_deprecate_relationships(self, relationship_ids):
        if not self.role in [OntologyRole.EDITOR, OntologyRole.ADMIN]:
            raise UnauthorisedOperationError("Only admins and editors can cancel deprecate relationships")

        await self._load_relationship_lifecycles(relationship_ids)
        for relationship_id in relationship_ids:
            lifecycle = await self._get_relationship_lifecycle(relationship_id)
            if lifecycle.deprecated_with:
                raise IllegalOperationError(
                    f"Relationship {relationship_id} was deprecated with entries {lifecycle.deprecated_with}: "
                    f"cancel their deprecation instead"
                )
            lifecycle.cancel_deprecation()
        await self._save_relationship_lifecycles()

    async def remove_relationships(self, relationship_ids):
        if not self.role in [OntologyRole.EDITOR, OntologyRole.ADMIN]:
            raise UnauthorisedOperationError("Only admins and editors can remove relationships")
        await self._load_relationship_lifecycles(relationship_ids)
        current_version = await self.get_current_version()
        for relationship_id in relationship_ids:
            lifecycle = await self._get_relationship_lifecycle(relationship_id)
            if not lifecycle.current_phase==LifecyclePhase.REMOVED:
                lifecycle.set_version_removed(current_version)
        await self._save_relationship_lifecycles()

    # Type overloads for _create_entry
    @overload
    async def _create_entry(self, entry: SubjectInput, **kwargs) -> SubjectStored: ...
    @overload
    async def _create_entry(self, entry: TraitInput, **kwargs) -> TraitStored: ...
    @overload
    async def _create_entry(self, entry: ScaleInput, **kwargs) -> ScaleStored: ...
    @overload
    async def _create_entry(self, entry: TermInput, **kwargs) -> TermStored: ...
    @overload
    async def _create_entry(self, entry: ObservationMethodInput, **kwargs) -> ObservationMethodStored: ...
    @overload
    async def _create_entry(self, entry: ConditionInput, **kwargs) -> ConditionStored: ...
    @overload
    async def _create_entry(self, entry: ControlMethodInput, **kwargs) -> ControlMethodStored: ...
    @overload
    async def _create_entry(self, entry: LocationTypeInput, **kwargs) -> LocationTypeStored: ...
    @overload
    async def _create_entry(self, entry: LayoutTypeInput, **kwargs) -> LayoutTypeStored: ...
    @overload
    async def _create_entry(self, entry: DesignInput, **kwargs) -> DesignStored: ...
    @overload
    async def _create_entry(self, entry: RoleInput, **kwargs) -> RoleStored: ...
    @overload
    async def _create_entry(self, entry: TraitInput, **kwargs) -> TraitStored: ...
    @overload
    async def _create_entry(self, entry: ConditionInput, **kwargs) -> ConditionStored: ...
    @overload
    async def _create_entry(self, entry: VariableInput, **kwargs) -> VariableStored:  ...
    @overload
    async def _create_entry(self, entry: FactorInput, **kwargs) -> FactorStored:  ...
    @overload
    async def _create_entry(self, entry: RecordGroupTypeInput, **kwargs) -> RecordGroupTypeStored:...
    @overload
    async def _create_entry(self, entry: EventTypeInput, **kwargs) -> EventTypeStored:  ...
    @overload
    async def _create_entry(self, entry: OntologyEntryInput, **kwargs) -> OntologyEntryStored: ...

    async def _create_entry(
            self,
            entry: OntologyEntryInput,
            parents: list[int]|None = None,
            children: list[int]|None = None
    ) -> OntologyEntryStored:
        if self.user_id is None:
            raise UnauthorisedOperationError("Only registered users can contribute to the ontology")
        """Create a new ontology entry with validation and persistence."""
        self._validate_attributes(entry)
        await self._validate_entry_uniqueness(entry)
        await self._require_citable_references(entry.references)
        # Create and persist entry

        created_entry = await self.persistence.create_entry(entry, self.user_id)
        await self._create_entry_lifecycle(created_entry.id)
        await self._save_entry_lifecycles()

        # Handle parent/child relationships
        for parent_id in (parents or []):
            relationship = ParentRelationship.build(
                parent_id=parent_id,
                child_id=created_entry.id,
                source_label = entry.label,
                target_label = entry.label
            )
            relationship = await self.create_relationship(relationship)
            await self._create_relationship_lifecycle(relationship.id)
        for child_id in (children or []):
            relationship = ParentRelationship.build(
                parent_id=created_entry.id,
                child_id=child_id,
                source_label = entry.label,
                target_label = entry.label
            )
            relationship = await self.create_relationship(relationship)
            await self._create_relationship_lifecycle(relationship.id)
        await self._save_relationship_lifecycles()
        return created_entry

    async def create_entry(
            self,
            entry: SubjectInput|TermInput|ObservationMethodInput|\
                   ControlMethodInput|\
                   LocationTypeInput|LayoutTypeInput|DesignInput|RoleInput|RecordGroupTypeInput,
            parents: list[int]|None = None,
            children: list[int]|None = None
    ):
        """Create a simple ontology entry (these types only support parent/children relationships on creation"""
        # Validate that this entry type is appropriate for direct creation
        entry = await self._create_entry(entry=entry, parents=parents, children=children)
        return entry

    async def create_entry_with_subjects(
            self,
            entry: TraitInput|ConditionInput,
            parents: List[int]|None = None,
            children: List[int]|None = None,
            subjects: List[int]|None = None
    ) -> TraitStored|ConditionStored:
        created_entry = await self._create_entry(entry=entry, parents=parents, children=children)
        if not isinstance(created_entry, (TraitStored, ConditionStored)):
            raise ValueError("Subjects may only be defined for Trait and Condition ontology entries")
        if subjects:
            for subject_id in subjects:
                relationship = SubjectRelationship.build(
                    source_id=created_entry.id,
                    subject_id=subject_id,
                    source_label=created_entry.label
                )
                await self.create_relationship(relationship)
        return created_entry

    async def create_scale(
            self,
            scale: ScaleInput,
            parents: List[int] = None,
            children: List[int] = None
    )-> ScaleStored:
        """A scale, with its categories if it is nominal or ordinal"""
        return await self._create_entry(entry=scale, parents=parents, children=children)

    async def create_subject(
            self,
            subject: SubjectInput,
            parents: List[int] = None,
            children: List[int] = None,
            traits: List[int] = None,
            conditions: List[int] = None
    ) -> SubjectStored:
        created_subject  = await self._create_entry(entry=subject, parents=parents, children=children)
        if traits:
            for trait_id in traits:
                relationship = SubjectRelationship.build(
                    source_id=trait_id,
                    subject_id=created_subject.id,
                    source_label=OntologyEntryLabel.TRAIT,
                    target_label=created_subject.label
                )
                await self.create_relationship(relationship)
        if conditions:
            for condition_id in conditions:
                relationship = SubjectRelationship.build(
                    source_id=condition_id,
                    subject_id=created_subject.id,
                    source_label=OntologyEntryLabel.CONDITION,
                    target_label=created_subject.label
                )
                await self.create_relationship(relationship)
        return created_subject

    async def create_trait(
            self,
            trait: TraitInput,
            parents: List[int] = None,
            children: List[int] = None,
            subjects: List[int] = None
    ) -> TraitStored:
        return await self.create_entry_with_subjects(entry=trait, parents=parents, children=children, subjects=subjects)

    async def create_condition(
            self,
            condition: ConditionInput,
            parents: List[int] = None,
            children: List[int] = None,
            subjects: List[int] = None
    ) -> ConditionStored:
        return await self.create_entry_with_subjects(entry=condition, parents=parents, children=children, subjects=subjects)

    async def create_variable(
            self,
            variable_input: VariableInput,
            trait_id: int,
            observation_method_id: int,
            scale_id: int,
            parents: List[int] = None,
            children: List[int] = None
    ) -> VariableStored:
        # Domain validation - parameters require all three components
        if not trait_id:
            raise ValueError("Parameters must describe a trait (trait_id is required)")
        if not observation_method_id:
            raise ValueError("Parameters must use an observation method (observation_method_id is required)")
        if not scale_id:
            raise ValueError("Parameters must use a scale (scale_id is required)")

        """Create a variable with its required component relationships (trait, method, scale)."""
        # Create the base entry using existing create_entry method
        variable = await self._create_entry(entry=variable_input, parents=parents, children=children)

        # Create all three required component relationships
        trait_rel = VariableComponentRelationship.TraitRelationship.build(
            variable_id=variable.id,
            trait_id=trait_id
        )
        await self.create_relationship(trait_rel)

        method_rel = VariableComponentRelationship.ObservationMethodRelationship.build(
            variable_id=variable.id,
            observation_method_id=observation_method_id
        )
        await self.create_relationship(method_rel)

        scale_rel = VariableComponentRelationship.ScaleRelationship.build(
            variable_id=variable.id,
            scale_id=scale_id
        )
        await self.create_relationship(scale_rel)

        return variable

    async def create_factor(
            self,
            factor_input: FactorInput,
            condition_id: int,
            control_method_id: int,
            scale_id: int,
            parents: List[int] = None,
            children: List[int] = None
    ) -> FactorStored:
        """Create a factor with its required component relationships (condition, method, scale)."""

        # Domain validation - parameters require all three components
        if not condition_id:
            raise ValueError("Parameters must describe a condition (condition_id is required)")
        if not control_method_id:
            raise ValueError("Parameters must use a control method (method_id is required)")
        if not scale_id:
            raise ValueError("Parameters must use a scale (scale_id is required)")

        # Create the base entry using existing create_entry method
        factor = await self._create_entry(factor_input, parents=parents, children=children)

        # Create all three required component relationships
        condition_rel = FactorComponentRelationship.ConditionRelationship.build(
            factor_id=factor.id,
            condition_id=condition_id
        )
        await self.create_relationship(condition_rel)

        method_rel = FactorComponentRelationship.ControlMethodRelationship.build(
            factor_id=factor.id,
            control_method_id=control_method_id
        )
        await self.create_relationship(method_rel)

        scale_rel = FactorComponentRelationship.ScaleRelationship.build(
            factor_id=factor.id,
            scale_id=scale_id
        )
        await self.create_relationship(scale_rel)

        return factor

    async def create_event_type(
            self,
            event_type_input: EventTypeInput,
            parents: List[int] = None,
            children: List[int] = None,
            variables: List[int] = None,
            factors: List[int] = None
    ) -> EventTypeStored:
        """Create an event type with its optional component relationships"""
        # Create the base entry using existing create_entry method
        event_type = await self._create_entry(event_type_input, parents=parents, children=children)
        for variable in (variables or []):
            variable_rel = EventTypeComponentRelationship.VariableRelationship.build(
                event_type_id=event_type.id,
                variable_id=variable
            )
            await self.create_relationship(variable_rel)
        for factor in (factors or []):
            factor_rel = EventTypeComponentRelationship.FactorRelationship.build(
                event_type_id=event_type.id,
                factor_id=factor
            )
            await self.create_relationship(factor_rel)
        return event_type

    # Type overloads for get_entry based on label parameter
    @overload
    async def get_entry(self, entry_id: int|None = None, name: str|None = None, *, label: Literal[OntologyEntryLabel.SUBJECT]) -> SubjectStored|None: ...
    @overload
    async def get_entry(self, entry_id: int|None = None, name: str|None = None, *, label: Literal[OntologyEntryLabel.TRAIT]) -> TraitStored|None: ...
    @overload
    async def get_entry(self, entry_id: int|None = None, name: str|None = None, *, label: Literal[OntologyEntryLabel.SCALE]) -> ScaleStored|None: ...
    @overload
    async def get_entry(self, entry_id: int|None = None, name: str|None = None, *, label: Literal[OntologyEntryLabel.TERM]) -> TermStored|None: ...
    @overload
    async def get_entry(self, entry_id: int|None = None, name: str|None = None, *, label: Literal[OntologyEntryLabel.OBSERVATION_METHOD]) -> ObservationMethodStored|None: ...
    @overload
    async def get_entry(self, entry_id: int|None = None, name: str|None = None, *, label: Literal[OntologyEntryLabel.CONDITION]) -> ConditionStored|None: ...
    @overload
    async def get_entry(self, entry_id: int|None = None, name: str|None = None, *, label: Literal[OntologyEntryLabel.CONTROL_METHOD]) -> ControlMethodStored|None: ...
    @overload
    async def get_entry(self, entry_id: int|None = None, name: str|None = None, *, label: Literal[OntologyEntryLabel.LOCATION_TYPE]) -> LocationTypeStored|None: ...
    @overload
    async def get_entry(self, entry_id: int|None = None, name: str|None = None, *, label: Literal[OntologyEntryLabel.LAYOUT_TYPE]) -> LayoutTypeStored|None: ...
    @overload
    async def get_entry(self, entry_id: int|None = None, name: str|None = None, *, label: Literal[OntologyEntryLabel.DESIGN]) -> DesignStored|None: ...
    @overload
    async def get_entry(self, entry_id: int|None = None, name: str|None = None, *, label: Literal[OntologyEntryLabel.ROLE]) -> RoleStored|None: ...
    @overload
    async def get_entry(self, entry_id: int|None = None, name: str|None = None, *, label: Literal[OntologyEntryLabel.VARIABLE]) -> VariableStored|None: ...
    @overload
    async def get_entry(self, entry_id: int|None = None, name: str|None = None, *, label: Literal[OntologyEntryLabel.FACTOR]) -> FactorStored|None: ...
    @overload
    async def get_entry(self, entry_id: int|None = None, name: str|None = None, *, label: Literal[OntologyEntryLabel.EVENT]) -> EventTypeStored|None: ...
    @overload
    async def get_entry(self, entry_id: int|None = None, name: str|None = None, *, label: Literal[OntologyEntryLabel.RECORD_GROUP_TYPE]) -> RecordGroupTypeStored|None: ...



    @overload
    async def get_entry(self, entry_id: int|None = None, name: str|None = None, label: OntologyEntryLabel|None = None) -> OntologyEntryStored|None: ...

    async def get_entry(self, entry_id: int|None = None, name: str|None = None, label: OntologyEntryLabel|None = None) -> OntologyEntryStored|None:
        """Retrieve an ontology entry"""
        return await self.persistence.get_entry(entry_id=entry_id, name=name, label=label)

    async def get_relationships(
            self,
            version: Version | None = None,
            phases: List[LifecyclePhase] | None = None,
            labels: List[OntologyRelationshipLabel] | None = None,
            entry_ids: List[int] | None = None,
            source_ids: List[int] | None = None,
            target_ids: List[int] | None = None
    ) -> AsyncGenerator[OntologyRelationshipBase, None]:
        async for rel in self.persistence.get_relationships(
            version=version,
            phases=phases,
            labels=labels,
            entry_ids=entry_ids,
            source_ids=source_ids,
            target_ids=target_ids
        ):
            yield rel

    async def update_entry(
            self,
            entry: OntologyEntryStored,
    ) -> None:
        """Update an existing ontology entry with validation."""
        if not entry.id:
            raise ValueError("Entry must have an ID for updates")
        if not self.user_id:
            raise UnauthorisedOperationError("Only registered users can update entries")
        await self._validate_entry_uniqueness(entry)
        # only references added need checking: the entry may keep citing references others added that this user cannot
        # read, or that were cited before the ontology cited public references only
        stored = await self.persistence.get_entry(entry_id=entry.id)
        if stored is not None and stored.locked:
            changed = [attr for attr in entry.LOCKED_ATTRIBUTES if getattr(entry, attr) != getattr(stored, attr)]
            if changed:
                raise UnauthorisedOperationError(
                    f"{stored.label.value} {stored.name} is locked, so its {', '.join(changed)} cannot change"
                )
        self._validate_attributes(entry)
        await self._require_citable_references(set(entry.references) - set(stored.references if stored else []))

        lifecycle = await self._get_entry_lifecycle(entry.id)
        if lifecycle.current_phase != LifecyclePhase.DRAFT:
            if not self.role in [OntologyRole.EDITOR, OntologyRole.ADMIN]:
                raise UnauthorisedOperationError("Only Editors and Admins may alter entries that have progressed beyond Draft")

        # Update entry
        await self.persistence.update_entry(entry, user_id=self.user_id)


    async def _validate_entry_types_for_relationship(
            self,
            relationship: OntologyRelationshipBase
    ) -> None:
        entry_types = await self.persistence.get_entry_types([relationship.source_id, relationship.target_id])

        if relationship.label is OntologyRelationshipLabel.PARENT_OF:
            # Parent-child validation
            self._validate_parent_child_relationships(relationship, entry_types)
        elif relationship.label is OntologyRelationshipLabel.HAS_TERM:
            # RELATES_TO validation
            self._validate_relates_to_relationships(relationship, entry_types)
        else:
            """Validate relationships have correct types."""
            valid_combinations = ontology_mapper.relationship_to_valid_source_and_target()

            expected = valid_combinations.get(relationship.label)
            if not expected:
                raise NotImplementedError(f"Validation required for relationship label: {relationship.label}")

            expected_sources, expected_targets = expected

            source_type = entry_types.get(relationship.source_id)
            target_type = entry_types.get(relationship.target_id)

            if source_type not in expected_sources:
                raise ValueError(f"Invalid {relationship.label}: source must be one of {expected_sources}, got {source_type}")
            if target_type not in expected_targets:
                raise ValueError(f"Invalid {relationship.label}: target must be one of {expected_targets}, got {target_type}")

    @staticmethod
    def _validate_parent_child_relationships(
            relationship: OntologyRelationshipBase,
            entry_types: Dict[int, str]
    ) -> None:
        """Validate that parent-child relationships connect entries of the same type."""
        if relationship.label != OntologyRelationshipLabel.PARENT_OF:
            return  # Not a parent relationship, skip validation

        parent_type = entry_types.get(relationship.source_id)
        child_type = entry_types.get(relationship.target_id)

        if parent_type != child_type:
            raise ValueError(
                f"Parent-child relationships must connect entries of the same type: "
                f"parent is {parent_type}, child is {child_type}"
            )

    @staticmethod
    def _validate_relates_to_relationships(
            relationship: OntologyRelationshipBase,
            entry_types: Dict[int, str]
    ) -> None:
        """Validate that RELATES_TO relationships connect non-Terms to Terms."""
        if relationship.label != OntologyRelationshipLabel.HAS_TERM:
            return  # Not a relates_to relationship, skip validation

        source_type = entry_types.get(relationship.source_id)
        sink_type = entry_types.get(relationship.target_id)

        # For RELATES_TO: sink must be Term, source must NOT be Term
        if sink_type != "Term":
            raise ValueError(
                f"RELATES_TO relationships must have a Term as the target (sink). "
                f"Got {sink_type} as target."
            )

        if source_type == "Term":
            raise ValueError(
                f"RELATES_TO relationships cannot have a Term as the source. "
                f"Terms connect to other Terms through parent/child relationships only."
            )

    async def create_relationship(self, relationship: OntologyRelationshipBase) -> OntologyRelationshipBase:
        """Create a new relationship """
        if self.user_id is None:
            raise UnauthorisedOperationError("Only registered users can contribute to the ontology")
        logger.debug(f"Creating relationship: {relationship}")
        await self._validate_entry_types_for_relationship(relationship)
        await self._require_unlocked_sources([relationship])
        await self._validate_no_circular_dependency(relationship)
        await self._validate_entries_exist([relationship.source_id, relationship.target_id])
        await self._require_current([relationship.source_id, relationship.target_id])

        async for rel in self._get_existing_relationship(relationship):
            # if removed we can create a new one, this preserves history for snapshots
            lifecycle = await self._get_relationship_lifecycle(relationship_id=rel.id)
            if lifecycle.current_phase == LifecyclePhase.REMOVED:
                continue
            elif lifecycle.current_phase == LifecyclePhase.ACTIVE:
                raise RelationshipExistsError("Relationship is already active")
            elif lifecycle.current_phase == LifecyclePhase.DRAFT:
                raise RelationshipExistsError("Relationship is already drafted")
            elif lifecycle.current_phase == LifecyclePhase.DEPRECATED:
                # for deprecated we allow reverting to former phase
                await self.cancel_deprecate_relationships(relationship_ids=[rel.id])
                return rel

        relationship = await self.persistence.create_relationship(relationship, user_id=self.user_id)
        await self._create_relationship_lifecycle(relationship.id)
        await self._save_relationship_lifecycles()
        return relationship

    async def link_to_term(self, source_id, source_label, term_id):
        relationship = TermRelationship.build(source_id=source_id, term_id=term_id, source_label=source_label)
        await self.create_relationship(relationship)

    async def deprecate_entry_relationships(self, relationships: List[OntologyRelationshipBase]) -> None:
        """Deprecate relationships an entry update dropped, keeping those that define a locked entry"""
        await self._require_unlocked_sources(relationships)
        await self.deprecate_relationships([relationship.id for relationship in relationships])

    # Lifecycle management
    async def activate_entry(
            self,
            entry_id: int,
            version: Version
    ) -> None:
        """Commit a draft entry."""
        lifecycle = await self._get_entry_lifecycle(entry_id)
        lifecycle.set_version_activated(version)
        await self._save_entry_lifecycles()

    async def activate_relationship(
            self,
            relationship_id: int,
            version: Version
    ) -> None:
        """Commit a draft entry."""
        lifecycle = await self._get_relationship_lifecycle(relationship_id)
        lifecycle.set_version_activated(version)
        await self._save_entry_lifecycles()

    async def get_cited_entry(self, entry_id: int, label: OntologyEntryLabel|None = None) -> OntologyEntryOutput|None:
        """
        An entry as data that cites it reads it, whatever its phase, a deprecated or removed one as it stood when it was
        deprecated: as the referential view gives it, but in this transaction. A new link needs an entry of a committed
        version (require_entries).
        """
        entries = await self.persistence.get_cited_entries([entry_id])
        if not entries or (label is not None and entries[0].label is not label):
            return None
        return entries[0]

    async def get_concept_scale(self, concept_id: int) -> ScaleOutput:
        """As cited: the scale of a variable or factor, with the categories of an ordinal or nominal scale in order"""
        concept = await self.get_cited_entry(concept_id)
        if not isinstance(concept, (VariableOutput, FactorOutput)):
            raise NoResultFoundError(f"Variable or factor {concept_id} not found")
        scale = await self.get_cited_entry(concept.scale, label=OntologyEntryLabel.SCALE) if concept.scale else None
        if scale is None:
            raise NoResultFoundError(f"The scale of {concept.label.value} {concept_id} was not found")
        return scale

    async def _create_entry_lifecycle(self, entry_id: int) -> EntryLifecycle:
        """Create a new entry lifecycle."""
        current_version = await self.persistence.get_current_version()
        if entry_id in self._entry_lifecycles:
            raise ValueError(f"Entry {entry_id} already has a lifecycle")
        lifecycle = EntryLifecycle(entry_id=entry_id, drafted=current_version)
        self._entry_lifecycles[entry_id] = lifecycle
        return lifecycle

    async def _load_entry_lifecycles(self, entry_ids: List[int]) -> None:
        """Load entry lifecycles for a list of entry ids to perform update operations."""
        lifecycles = await self.persistence.get_entry_lifecycles(entry_ids)
        self._entry_lifecycles.update(lifecycles)
        self._stored_entry_versions.update({i: lifecycle.snapshot() for i, lifecycle in lifecycles.items()})

    async def _load_relationship_lifecycles(self, relationship_ids: List[int]) -> None:
        """Load entry lifecycles for a list of entry ids to perform update operations."""
        lifecycles = await self.persistence.get_relationship_lifecycles(relationship_ids)
        self._relationship_lifecycles.update(lifecycles)
        self._stored_relationship_versions.update({i: lifecycle.snapshot() for i, lifecycle in lifecycles.items()})

    async def _create_relationship_lifecycle(
            self,
            relationship_id: int
    ) -> RelationshipLifecycle:
        """Create a new relationship lifecycle."""
        current_version = await self.persistence.get_current_version()
        lifecycle = RelationshipLifecycle(
            relationship_id=relationship_id,
            drafted=current_version
        )
        self._relationship_lifecycles[relationship_id] = lifecycle
        return lifecycle

    async def _get_entry_lifecycle(self, entry_id: int) -> EntryLifecycle:
        """Get entry lifecycle or raise exception."""
        lifecycle = self._entry_lifecycles.get(entry_id)
        if not lifecycle:
            await self._load_entry_lifecycles([entry_id])
            lifecycle = self._entry_lifecycles.get(entry_id)
            if not lifecycle:
                raise ValueError(f"No lifecycle found for entry {entry_id}")
        return lifecycle

    async def _get_relationship_lifecycle(self, relationship_id: int) -> RelationshipLifecycle:
        """Get relationship lifecycle or raise exception."""
        lifecycle = self._relationship_lifecycles.get(relationship_id)
        if not lifecycle:
            await self._load_relationship_lifecycles([relationship_id])
            lifecycle = self._relationship_lifecycles.get(relationship_id)
            if not lifecycle:
                raise ValueError(f"No lifecycle found for relationship {relationship_id}")
        return lifecycle

    @staticmethod
    def _changed_lifecycles(lifecycles: Dict[int, EntryLifecycle | RelationshipLifecycle], stored_versions: Dict[int, Dict[str, int]]) -> Dict:
        """The lifecycles whose versions differ from those last loaded or saved"""
        return {
            i: lifecycle for i, lifecycle in lifecycles.items()
            if stored_versions.get(i) != lifecycle.snapshot()
        }

    async def _save_entry_lifecycles(self) -> None:
        """Save the entry lifecycles that changed to persistence."""
        if not self.user_id:
            raise UnauthorisedOperationError("Only registered users can affect changes")
        changed = self._changed_lifecycles(self._entry_lifecycles, self._stored_entry_versions)
        if changed:
            await self.persistence.save_entry_lifecycles(changed, user_id=self.user_id)
            self._stored_entry_versions.update({i: lifecycle.snapshot() for i, lifecycle in changed.items()})

    async def _save_relationship_lifecycles(self) -> None:
        """Save the relationship lifecycles that changed to persistence."""
        if not self.user_id:
            raise UnauthorisedOperationError("Only registered users can affect changes")
        changed = self._changed_lifecycles(self._relationship_lifecycles, self._stored_relationship_versions)
        if changed:
            await self.persistence.save_relationship_lifecycles(changed, user_id=self.user_id)
            self._stored_relationship_versions.update({i: lifecycle.snapshot() for i, lifecycle in changed.items()})

    @staticmethod
    def _validate_attributes(entry: OntologyEntryInput|OntologyEntryStored) -> None:
        """What an entry's own attributes must satisfy: a scale's categories"""
        if isinstance(entry, ScaleBase):
            entry.validate_categories()

    # Persistence-dependent validation methods
    async def _validate_entry_uniqueness(
            self,
            entry: OntologyEntryInput|OntologyEntryStored
    ) -> None:
        """Validate entry name and abbreviation uniqueness."""
        if isinstance(entry, OntologyEntryStored):
            exclude_id = entry.id
        else:
            exclude_id = None
        if await self.persistence.name_in_use(entry.label, entry.name, exclude_id):
            raise IdentityExistsError(
                f"Another {entry.label} is using the name: {entry.name}"
            )
        if entry.abbreviation:
            if await self.persistence.abbreviation_in_use(entry.label, entry.abbreviation, exclude_id):
                raise IdentityExistsError(
                    f"Another {entry.label} is using the abbreviation {entry.abbreviation}"
                )

    async def _require_current(self, entry_ids: List[int]) -> None:
        """A relationship to a deprecated entry would outlast it, when the next commit removes the entry"""
        deprecated = [entry_id for entry_id in entry_ids if not is_current(await self._get_entry_lifecycle(entry_id))]
        if deprecated:
            raise IllegalOperationError(f"Entries {deprecated} are deprecated: relationships to them can't be added")

    async def require_entries(self, entry_ids: List[int], label: OntologyEntryLabel|None = None) -> None:
        """
        For links from outside the ontology that a change adds: each entry must exist, with the label if given, and be
        of a committed version: activated, and not removed. A draft is refused, as it may be removed before any version
        has it. Links already stored are not checked: what data cites is read whatever its phase (get_cited_entry), so
        data citing a removed entry can still be edited, but nothing new links to one.
        """
        entry_ids = list(dict.fromkeys(entry_ids))
        if not entry_ids:
            return
        found = {entry.id: entry for entry in await self.persistence.get_cited_entries(entry_ids)}
        missing = [entry_id for entry_id in entry_ids if entry_id not in found or (label is not None and found[entry_id].label is not label)]
        if missing:
            raise ValueError(f"Entries do not exist{f' for label {label.value}' if label else ''}: {missing}")

        def named(entries) -> str:
            return ", ".join(f"{entry.label.value} {entry.id} ({entry.name})" for entry in entries)

        removed = [found[entry_id] for entry_id in entry_ids if found[entry_id].phase is LifecyclePhase.REMOVED]
        if removed:
            raise IllegalOperationError(
                f"Removed from the ontology, so nothing new can be linked to it: {named(removed)}. Choose a current entry"
            )
        await self._load_entry_lifecycles(entry_ids)
        drafts = [found[entry_id] for entry_id in entry_ids if self._entry_lifecycles[entry_id].activated is None]
        if drafts:
            raise IllegalOperationError(
                f"Not yet in a committed version of the ontology, so nothing can be linked to it: {named(drafts)}. "
                f"Commit the version first"
            )

    async def _validate_entries_exist(self, entry_ids: List[int], label: OntologyEntryLabel|None = None):
        if label:
            exist_map = await self.persistence.entries_exist_for_label(entry_ids, label = label)
            missing = [key for key, value in exist_map.items() if not value]
            if missing:
                raise ValueError(f"Entries do not exist for label {label}: {missing}")
        else:
            exist_map = await self.persistence.entries_exist(entry_ids)
            missing = [key for key, value in exist_map.items() if not value]
            if missing:
                raise ValueError(f"Entries do not exist: {missing}")

    async def _validate_no_circular_dependency(self, relationship: OntologyRelationshipBase) -> None:
        """Validate that relationship won't create circular guards with the same label"""
        if await self.persistence.has_path_between_entries(
                relationship.target_id,
                relationship.source_id,
                relationship.label
        ):
            source_node = await self.get_entry(relationship.source_id)
            target_node = await self.get_entry(relationship.target_id)
            if source_node is None or target_node is None:
                raise ValueError("Unrecognized nodes in relationship")
            raise ValueError(
                f"Adding relationship would create circular dependency : "
                f"({source_node.name}) -[{relationship.label}]-> ({target_node.name})"
            )

    async def _get_existing_relationship(self, relationship: OntologyRelationshipBase) -> AsyncGenerator[OntologyRelationshipBase,None]:
        async for rel in self.persistence.get_relationships(
                source_ids = [relationship.source_id],
                target_ids = [relationship.target_id],
                labels=[relationship.label]
        ):
            yield rel

