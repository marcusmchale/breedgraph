from src.breedgraph.custom_exceptions import IllegalOperationError, RelationshipExistsError

from src.breedgraph.domain.model.ontology import *
from src.breedgraph.domain.model.accounts import OntologyRole
from src.breedgraph.domain.events import Event
from src.breedgraph.domain.events.ontology import OntologyVersionCreated

from src.breedgraph.service_layer.persistence import OntologyPersistenceService

from typing import Set, List, Tuple, Dict, Any, AsyncGenerator, overload, Literal, TypeVar

import logging

logger = logging.getLogger(__name__)

T = TypeVar("T", SubjectStored, TraitStored, ScaleStored)  # expand as needed

class OntologyApplicationService:
    """
    Unified application service for all ontology operations.
    Handles validation, state management, persistence, and event publishing.
    """
    def __init__(
            self,
            persistence_service: OntologyPersistenceService,
            user_id: int|None = None,
            role: OntologyRole|None = None,
    ):
        self.persistence = persistence_service
        self.user_id = user_id
        self.role = role
        self.events: List[Event] = []
        # in memory store for lifecycle management
        self._entry_lifecycles: Dict[int, EntryLifecycle] = {}
        self._relationship_lifecycles: Dict[int, RelationshipLifecycle] = {}

    def collect_events(self):
        while self.events:
            yield self.events.pop(0)

    async def get_current_version(self):
        return await self.persistence.get_current_version()

    async def commit_version(
            self,
            version_change: VersionChange|None = VersionChange.PATCH,
            comment: str = None,
            licence_reference: int = None,
            copyright_reference: int = None
    ) -> OntologyCommit:
        if not self.role in [OntologyRole.EDITOR, OntologyRole.ADMIN]:
            raise IllegalOperationError("Only admins and editors can commit versions")
        """Create a new ontology version with commit metadata."""
        # Save through persistence service
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
        await self.persistence.activate_drafts(version)

    async def remove_deprecated(self, version: Version):
        """Remove all deprecated entries at the corresponding version."""
        await self.persistence.remove_deprecated(version)

    async def activate_entries(self, entry_ids):
        if not self.role in [OntologyRole.EDITOR, OntologyRole.ADMIN]:
            raise IllegalOperationError("Only admins and editors can activate entries")
        await self._load_entry_lifecycles(entry_ids)
        current_version = await self.get_current_version()
        for entry_id in entry_ids:
            lifecycle = await self._get_entry_lifecycle(entry_id)
            if not lifecycle.current_phase==LifecyclePhase.ACTIVE:
                lifecycle.set_version_activated(current_version)
        await self._save_entry_lifecycles()

    async def deprecate_entries(self, entry_ids):
        if not self.role in [OntologyRole.EDITOR, OntologyRole.ADMIN]:
            raise IllegalOperationError("Only admins and editors can deprecate entries")
        await self._load_entry_lifecycles(entry_ids)
        current_version = await self.get_current_version()
        for entry_id in entry_ids:
            lifecycle = await self._get_entry_lifecycle(entry_id)
            if not lifecycle.current_phase==LifecyclePhase.DEPRECATED:
                lifecycle.set_version_deprecated(current_version)
        await self._save_entry_lifecycles()

    async def remove_entries(self, entry_ids):
        if not self.role in [OntologyRole.EDITOR, OntologyRole.ADMIN]:
            raise IllegalOperationError("Only admins and editors can remove entries")
        await self._load_entry_lifecycles(entry_ids)
        current_version = await self.get_current_version()
        for entry_id in entry_ids:
            lifecycle = await self._get_entry_lifecycle(entry_id)
            if not lifecycle.current_phase==LifecyclePhase.REMOVED:
                lifecycle.set_version_removed(current_version)
        await self._save_entry_lifecycles()

    async def activate_relationships(self, relationship_ids):
        if not self.role in [OntologyRole.EDITOR, OntologyRole.ADMIN]:
            raise IllegalOperationError("Only admins and editors can activate relationships")
        await self._load_relationship_lifecycles(relationship_ids)
        current_version = await self.get_current_version()
        for relationship_id in relationship_ids:
            lifecycle = await self._get_relationship_lifecycle(relationship_id)
            if not lifecycle.current_phase==LifecyclePhase.ACTIVE:
                lifecycle.set_version_activated(current_version)
        await self._save_relationship_lifecycles()

    async def deprecate_relationships(self, relationship_ids):
        if not self.role in [OntologyRole.EDITOR, OntologyRole.ADMIN]:
            raise IllegalOperationError("Only admins and editors can deprecate relationships")
        await self._load_relationship_lifecycles(relationship_ids)
        current_version = await self.get_current_version()
        for relationship_id in relationship_ids:
            lifecycle = await self._get_relationship_lifecycle(relationship_id)
            if not lifecycle.current_phase==LifecyclePhase.DEPRECATED:
                lifecycle.set_version_deprecated(current_version)
        await self._save_relationship_lifecycles()

    async def remove_relationships(self, relationship_ids):
        if not self.role in [OntologyRole.EDITOR, OntologyRole.ADMIN]:
            raise IllegalOperationError("Only admins and editors can remove relationships")
        await self._load_relationship_lifecycles(relationship_ids)
        current_version = await self.get_current_version()
        for relationship_id in relationship_ids:
            lifecycle = await self._get_relationship_lifecycle(relationship_id)
            if not lifecycle.current_phase==LifecyclePhase.REMOVED:
                lifecycle.set_version_removed(current_version)
        await self._save_relationship_lifecycles()

    #async def get_version_commit_info(self, version_id: Version) -> OntologyCommit:
    #    """Retrieve commit information for a specific version."""
    #    return await self.persistence.get_commit(version_id)

    async def get_commit_history(self, limit: int = 10) -> AsyncGenerator[OntologyCommit, None]:
        """Get version history with commit metadata, ordered by commit time."""
        async for commit in self.persistence.get_commit_history(limit=limit):
            yield commit

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
    async def _create_entry(self, entry: ScaleCategoryInput, **kwargs) -> ScaleCategoryStored: ...
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
    async def _create_entry(self, entry: TitleInput, **kwargs) -> TitleStored: ...
    @overload
    async def _create_entry(self, entry: TraitInput, **kwargs) -> TraitStored: ...
    @overload
    async def _create_entry(self, entry: ConditionInput, **kwargs) -> ConditionStored: ...
    @overload
    async def _create_entry(self, entry: VariableInput, **kwargs) -> VariableStored:  ...
    @overload
    async def _create_entry(self, entry: FactorInput, **kwargs) -> FactorStored:  ...
    @overload
    async def _create_entry(self, entry: EventTypeInput, **kwargs) -> EventTypeStored:  ...
    @overload
    async def _create_entry(self, entry: OntologyEntryInput, **kwargs) -> OntologyEntryStored: ...

    async def _create_entry(
            self,
            entry: OntologyEntryInput,
            parents: list[int] = None,
            children: list[int] = None
    ) -> OntologyEntryStored:
        """Create a new ontology entry with validation and persistence."""
        await self._validate_entry_uniqueness(entry)
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
                   ScaleCategoryInput|ControlMethodInput|\
                   LocationTypeInput|LayoutTypeInput|DesignInput|RoleInput|TitleInput,
            parents: list[int] = None,
            children: list[int] = None
    ):
        """Create a simple ontology entry (these types only support parent/children relationships on creation"""
        # Validate that this entry type is appropriate for direct creation
        entry = await self._create_entry(entry=entry, parents=parents, children=children)
        return entry

    async def create_entry_with_subjects(
            self,
            entry: TraitInput|ConditionInput,
            parents: List[int] = None,
            children: List[int] = None,
            subjects: List[int] = None
    ) -> TraitStored|ConditionStored:
        created_entry = await self._create_entry(entry=entry, parents=parents, children=children)
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
            children: List[int] = None,
            categories: List[int]|None = None
    )-> ScaleStored:
        created_scale = await self._create_entry(entry=scale, parents=parents, children=children)
        if categories:
            if not scale.scale_type in [ScaleType.ORDINAL, ScaleType.NOMINAL]:
                raise ValueError("Categories are only valid for Ordinal and Nominal scales")
            for rank,category_id in enumerate(categories):
                relationship = CategoryRelationship.build(
                    scale_id=created_scale.id,
                    category_id=category_id,
                    rank=rank if scale.scale_type is ScaleType.ORDINAL else None
                )
                await self.create_relationship(relationship)
        return created_scale

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



    # Type overloads for get_entry based on label parameter and as_output
    @overload
    async def get_entry(self, entry_id: int = None, name: str = None, *, label: Literal["SUBJECT"], as_output: Literal[False] = False) -> SubjectStored|None: ...
    @overload
    async def get_entry(self, entry_id: int = None, name: str = None, *, label: Literal["TRAIT"], as_output: Literal[False] = False) -> TraitStored|None: ...
    @overload
    async def get_entry(self, entry_id: int = None, name: str = None, *, label: Literal["SCALE"], as_output: Literal[False] = False) -> ScaleStored|None: ...
    @overload
    async def get_entry(self, entry_id: int = None, name: str = None, *, label: Literal["TERM"], as_output: Literal[False] = False) -> TermStored|None: ...
    @overload
    async def get_entry(self, entry_id: int = None, name: str = None, *, label: Literal["OBSERVATION_METHOD"], as_output: Literal[False] = False) -> ObservationMethodStored|None: ...
    @overload
    async def get_entry(self, entry_id: int = None, name: str = None, *, label: Literal["CONDITION"], as_output: Literal[False] = False) -> ConditionStored|None: ...
    @overload
    async def get_entry(self, entry_id: int = None, name: str = None, *, label: Literal["CATEGORY"], as_output: Literal[False] = False) -> ScaleCategoryStored|None: ...
    @overload
    async def get_entry(self, entry_id: int = None, name: str = None, *, label: Literal["CONTROL_METHOD"], as_output: Literal[False] = False) -> ControlMethodStored|None: ...
    @overload
    async def get_entry(self, entry_id: int = None, name: str = None, *, label: Literal["LOCATION_TYPE"], as_output: Literal[False] = False) -> LocationTypeStored|None: ...
    @overload
    async def get_entry(self, entry_id: int = None, name: str = None, *, label: Literal["LAYOUT_TYPE"], as_output: Literal[False] = False) -> LayoutTypeStored|None: ...
    @overload
    async def get_entry(self, entry_id: int = None, name: str = None, *, label: Literal["DESIGN"], as_output: Literal[False] = False) -> DesignStored|None: ...
    @overload
    async def get_entry(self, entry_id: int = None, name: str = None, *, label: Literal["ROLE"], as_output: Literal[False] = False) -> RoleStored|None: ...
    @overload
    async def get_entry(self, entry_id: int = None, name: str = None, *, label: Literal["TITLE"], as_output: Literal[False] = False) -> TitleStored|None: ...
    @overload
    async def get_entry(self, entry_id: int = None, name: str = None, *, label: Literal["VARIABLE"], as_output: Literal[False] = False) -> VariableStored|None: ...
    @overload
    async def get_entry(self, entry_id: int = None, name: str = None, *, label: Literal["FACTOR"], as_output: Literal[False] = False) -> FactorStored|None: ...
    @overload
    async def get_entry(self, entry_id: int = None, name: str = None, *, label: Literal["EVENT"], as_output: Literal[False] = False) -> EventTypeStored|None: ...

    @overload
    async def get_entry(self, entry_id: int = None, name: str = None, *, label: Literal["SUBJECT"], as_output: Literal[True]) -> SubjectOutput|None: ...
    @overload
    async def get_entry(self, entry_id: int = None, name: str = None, *, label: Literal["TRAIT"], as_output: Literal[True]) -> TraitOutput|None: ...
    @overload
    async def get_entry(self, entry_id: int = None, name: str = None, *, label: Literal["SCALE"], as_output: Literal[True]) -> ScaleOutput|None: ...
    @overload
    async def get_entry(self, entry_id: int = None, name: str = None, *, label: Literal["TERM"], as_output: Literal[True]) -> TermOutput|None: ...
    @overload
    async def get_entry(self, entry_id: int = None, name: str = None, *, label: Literal["OBSERVATION_METHOD"], as_output: Literal[True]) -> ObservationMethodOutput|None: ...
    @overload
    async def get_entry(self, entry_id: int = None, name: str = None, *, label: Literal["CONDITION"], as_output: Literal[True]) -> ConditionOutput|None: ...
    @overload
    async def get_entry(self, entry_id: int = None, name: str = None, *, label: Literal["CATEGORY"], as_output: Literal[True]) -> ScaleCategoryOutput|None: ...
    @overload
    async def get_entry(self, entry_id: int = None, name: str = None, *, label: Literal["CONTROL_METHOD"], as_output: Literal[True]) -> ControlMethodOutput|None: ...
    @overload
    async def get_entry(self, entry_id: int = None, name: str = None, *, label: Literal["LOCATION_TYPE"], as_output: Literal[True]) -> LocationTypeOutput|None: ...
    @overload
    async def get_entry(self, entry_id: int = None, name: str = None, *, label: Literal["LAYOUT_TYPE"], as_output: Literal[True]) -> LayoutTypeOutput|None: ...
    @overload
    async def get_entry(self, entry_id: int = None, name: str = None, *, label: Literal["DESIGN"], as_output: Literal[True]) -> DesignOutput|None: ...
    @overload
    async def get_entry(self, entry_id: int = None, name: str = None, *, label: Literal["ROLE"], as_output: Literal[True]) -> RoleOutput|None: ...
    @overload
    async def get_entry(self, entry_id: int = None, name: str = None, *, label: Literal["TITLE"], as_output: Literal[True]) -> TitleOutput|None: ...
    @overload
    async def get_entry(self, entry_id: int = None, name: str = None, *, label: Literal["VARIABLE"], as_output: Literal[True]) -> VariableOutput|None: ...
    @overload
    async def get_entry(self, entry_id: int = None, name: str = None, *, label: Literal["FACTOR"], as_output: Literal[True]) -> FactorOutput|None: ...
    @overload
    async def get_entry(self, entry_id: int = None, name: str = None, *, label: Literal["EVENT"], as_output: Literal[True]) -> EventTypeOutput|None: ...
    
    @overload
    async def get_entry(self, entry_id: int = None, name: str = None, label: OntologyEntryLabel = None, as_output: Literal[False] = False) -> OntologyEntryStored|None: ...
    @overload
    async def get_entry(self, entry_id: int = None, name: str = None, label: OntologyEntryLabel = None, as_output: Literal[True] = False) -> OntologyEntryOutput|None: ...

    async def get_entry(self, entry_id: int = None, name: str = None, label: OntologyEntryLabel = None, as_output: bool = False) -> OntologyEntryStored|OntologyEntryOutput|None:
        """Retrieve an ontology entry"""
        return await self.persistence.get_entry(entry_id=entry_id, name=name, label=label, as_output=as_output)

    async def get_scale_id(self, entry_id: int) -> int|None:
        async for relationship in self.persistence.get_relationships(
                entry_ids = [entry_id],
                labels=[OntologyRelationshipLabel.USES_SCALE]
        ):
            return relationship.target_id
        return None

    async def get_entries(
            self,
            version: Version | None = None,
            phases: List[LifecyclePhase] | None = None,
            entry_ids: List[int] | None = None,
            labels: List[OntologyEntryLabel] | None = None,
            names: List[str] | None = None,
            as_output: bool = False
    ) -> AsyncGenerator[OntologyEntryStored | OntologyEntryOutput, None]:
        async for entry in self.persistence.get_entries(
            version=version,
            entry_ids=entry_ids,
            phases=phases,
            labels=labels,
            names=names,
            as_output=as_output
        ):
            yield entry



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
            target_ids=target_ids,
        ):
            yield rel

    async def update_entry(
            self,
            entry: OntologyEntryStored,
    ) -> None:
        """Update an existing ontology entry with validation."""
        if not entry.id:
            raise ValueError("Entry must have an ID for updates")

        # Only persistence-dependent validations - Pydantic handles structure
        await self._validate_entry_uniqueness(entry)

        lifecycle = await self._get_entry_lifecycle(entry.id)
        if lifecycle.current_phase != LifecyclePhase.DRAFT:
            if not self.role in [OntologyRole.EDITOR, OntologyRole.ADMIN]:
                raise IllegalOperationError("Only Editors and Admins may alter entries that have progressed beyond Draft")
            # any edit reverts the entry to draft
            current_version = await self.get_current_version()
            await self.revert_entry_to_draft(entry.id, current_version)

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
        logger.debug(f"Creating relationship: {relationship}")
        # Fetch entry types once for all validators that need them
        # entry type relationship specific validation
        await self._validate_entry_types_for_relationship(relationship)
        await self._validate_no_circular_dependency(relationship)
        await self._validate_entries_exist([relationship.source_id, relationship.target_id])
        # Create relationship if it doesn't exist, else revert it to draft'
        relationship_id = None
        async for rel in self.persistence.get_relationships(
                source_ids = [relationship.source_id],
                target_ids = [relationship.target_id],
                labels=[relationship.label]
        ):
            relationship_id = rel.id
        if relationship_id is None:
            relationship = await self.persistence.create_relationship(relationship)
            # Create and save lifecycle
            await self._create_relationship_lifecycle(relationship.id)
            await self._save_relationship_lifecycles()
        else:
            relationship.id = relationship_id
            await self.update_relationship(relationship)
        return relationship

    async def link_to_term(self, source_id, source_label, term_id):
        relationship = TermRelationship.build(source_id=source_id, term_id=term_id, source_label=source_label)
        await self.create_relationship(relationship)

    async def link_to_category(self, scale_id, category_id):
        relationship = CategoryRelationship.build(scale_id=scale_id, category_id=category_id, source_label=OntologyEntryLabel.SCALE)
        await self.create_relationship(relationship)

    async def update_relationship(self, relationship: OntologyRelationshipBase) -> None:
        """Update the properties of a relationship"""
        # Update reverts any relationship to draft phase
        lifecycle = await self._get_relationship_lifecycle(relationship.id)
        if lifecycle.current_phase != LifecyclePhase.DRAFT:
            if not self.role in [OntologyRole.EDITOR, OntologyRole.ADMIN]:
                raise IllegalOperationError("Only Editors and Admins may alter relationships that have progressed beyond Draft")
            # any edit reverts the relationship to draft
            current_version = await self.get_current_version()
            await self.revert_relationship_to_draft(relationship.id, current_version)

        await self.persistence.update_relationship(relationship)

    # Lifecycle management
    async def revert_entry_to_draft(
            self,
            entry_id: int,
            version: Version
    ) -> None:
        """Commit a draft entry."""
        lifecycle = await self._get_entry_lifecycle(entry_id)
        lifecycle.set_version_drafted(version)
        await self._save_entry_lifecycles()

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

    async def revert_relationship_to_draft(
            self,
            relationship_id: int,
            version: Version
    ) -> None:
        """Commit a draft entry."""
        lifecycle = await self._get_relationship_lifecycle(relationship_id)
        lifecycle.set_version_drafted(version)
        await self._save_relationship_lifecycles()

    async def activate_relationship(
            self,
            relationship_id: int,
            version: Version
    ) -> None:
        """Commit a draft entry."""
        lifecycle = await self._get_relationship_lifecycle(relationship_id)
        lifecycle.set_version_activated(version)
        await self._save_entry_lifecycles()

    async def deprecate_entry(
            self,
            entry_id: int,
            version: Version
    ) -> None:
        """Deprecate an active entry."""
        lifecycle = await self._get_entry_lifecycle(entry_id)
        lifecycle.set_version_deprecated(version)
        await self._save_entry_lifecycles()

    async def remove_entry(
            self,
            entry_id: int,
            version: Version
    ) -> None:
        """Remove an entry after validating no dependencies exist."""
        # Check for dependencies
        dependencies = await self.persistence.get_entry_dependencies(entry_id)
        if dependencies:
            raise ValueError(
                f"Cannot remove entry {entry_id}, it has dependencies: {dependencies}"
            )

        lifecycle = await self._get_entry_lifecycle(entry_id)
        lifecycle.set_version_removed(version)
        await self._save_entry_lifecycles()

    async def get_scale_category_ids(self, scale_id: int) -> List[int]:
        relationships = [rel async for rel in self.persistence.get_relationships(
                entry_ids = [scale_id], labels = [OntologyRelationshipLabel.HAS_CATEGORY]
        )]
        relationships.sort(key=lambda x: x.rank or x.id)
        return [rel.target_id for rel in relationships]

    # Scale operations
    async def add_scale_categories(
            self,
            scale_id: int,
            categories: List[int],
            ranks: List[int] | None = None
    ) -> None:
        """Add categories to a scale"""
        # Basic validation
        await self._validate_entries_exist(categories, label=ScaleCategoryBase.label)
        scale = await self.get_entry(entry_id=scale_id, label=OntologyEntryLabel.SCALE)
        scale_categories = await self.get_scale_category_ids(scale_id)

        if not scale:
            raise ValueError("Scale not found")

        if scale.scale_type is ScaleType.NOMINAL:
            if ranks:
                raise ValueError("Ranks are only valid for Ordinal scales")
            for category_id in categories:
                if category_id in scale_categories:
                    logger.debug(f"Scale category {category_id} already in use for scale {scale_id}")
                    continue
                relationship = CategoryRelationship.build(
                    scale_id=scale.id,
                    category_id=category_id
                )
                await self.create_relationship(relationship)

        elif scale.scale_type is ScaleType.ORDINAL:
            if not ranks:
                # append to existing ranks
                for rank, category_id in enumerate(categories, start=len(scale_categories)):
                    relationship = CategoryRelationship.build(
                        scale_id=scale.id,
                        category_id=category_id,
                        rank=rank
                    )
                    await self.create_relationship(relationship)
            else:
                if not len(ranks) == len(categories):
                    raise ValueError("If providing ranks, a rank must be provided for all categories")
                scale_categories = scale_categories or []
                # May beed to update the old ranks, so insert the new ones to get the updated ranks
                # first sort them so insertion logic works such that the final position is defined by rank
                categories, ranks = zip(*sorted(zip(categories, ranks), key=lambda x: x[1]))
                # then insert
                for i, category_id in enumerate(categories):
                    scale_categories.insert(ranks[i], category_id)

                # create and update relationships
                for i, category_id in enumerate(scale_categories):
                    if category_id in categories:
                        # New relationship
                        relationship = CategoryRelationship.build(
                            scale_id=scale.id,
                            category_id=category_id,
                            rank=ranks[i]
                        )
                        await self.create_relationship(relationship)
                    else:
                        # Old relationship, update rank
                        rel = CategoryRelationship.build(scale_id=scale_id, category_id=category_id, rank=ranks[i])
                        await self.update_relationship(rel)
        else:
            raise ValueError("Categories are only valid for Ordinal and Nominal scales")

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

    async def _load_relationship_lifecycles(self, relationship_ids: List[int]) -> None:
        """Load entry lifecycles for a list of entry ids to perform update operations."""
        lifecycles = await self.persistence.get_relationship_lifecycles(relationship_ids)
        self._relationship_lifecycles.update(lifecycles)

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

    async def _save_entry_lifecycles(self) -> None:
        """Save entry lifecycles to persistence."""
        await self.persistence.save_entry_lifecycles(self._entry_lifecycles, user_id = self.user_id)

    async def _save_relationship_lifecycles(self) -> None:
        """Save relationship lifecycles to persistence."""
        await self.persistence.save_relationship_lifecycles(self._relationship_lifecycles, user_id=self.user_id)

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
            raise ValueError(
                f"Another {entry.label} is using the name: {entry.name}"
            )
        if entry.abbreviation:
            if await self.persistence.abbreviation_in_use(entry.label, entry.abbreviation, exclude_id):
                raise ValueError(
                    f"Another {entry.label} is using the abbreviation {entry.abbreviation}"
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

    #todo consider a domain service to implement these sorts of checks, we now have a few of them and the application service is getting busy.
    async def _validate_no_circular_dependency(self, relationship: OntologyRelationshipBase) -> None:
        """Validate that relationship won't create circular dependencies with the same label"""
        if await self.persistence.has_path_between_entries(
                relationship.target_id,
                relationship.source_id,
                relationship.label
        ):
            raise ValueError(
                f"Adding relationship would create circular dependency : "
                f"{relationship.source_id} -[{relationship.label}]-> {relationship.target_id}"
            )

    async def _validate_relationship_does_not_exist(self, relationship: OntologyRelationshipBase):
        async for rel in self.persistence.get_relationships(
                source_ids = [relationship.source_id],
                target_ids = [relationship.target_id],
                labels=[relationship.label]
        ):
            raise RelationshipExistsError(f"Relationship already exists: {str(rel)}")

