from typing import Optional, Dict, List, Set, Tuple, Any, AsyncGenerator
from collections import defaultdict

from src.breedgraph.service_layer.persistence import OntologyPersistenceService
from src.breedgraph.domain.model.ontology import *
from src.breedgraph.domain.model.accounts import OntologyRole


class MockOntologyPersistenceService(OntologyPersistenceService):
    """Mock implementation for testing ontology application service."""

    def __init__(self):
        # for testing
        self.ontology_role = OntologyRole.ADMIN

        # Storage for entries
        self.entries: Dict[int, OntologyEntryStored] = {}
        self.next_entry_id = 1

        # Storage for relationships
        self.relationships: Dict[int, OntologyRelationshipBase] = {}
        self.next_relationship_id = 1

        # Storage for lifecycles
        self.entry_lifecycles: Dict[int, EntryLifecycle] = {}
        self.relationship_lifecycles: Dict[int, RelationshipLifecycle] = {}

        # Storage for scale categories
        self.scale_categories: Dict[int, List[Tuple[int, Optional[int]]]] = defaultdict(list)

        # Storage for versions
        self.commits: Dict[Version, OntologyCommit] = {}
        self.commit_history: List[OntologyCommit] = []

        # Tracking names and abbreviations by label
        self.names_by_label: Dict[str, Set[str]] = defaultdict(set)
        self.abbreviations_by_label: Dict[str, Set[str]] = defaultdict(set)

    def reset(self):
        """Reset all stored data - useful for test cleanup."""
        self.__init__()

    def get_user_ontology_role(self, user_id: int):
        return self.ontology_role

    async def _create_entry(self, entry: OntologyEntryInput, user_id: int) -> OntologyEntryStored:
        """Create a new ontology entry and return it in stored form."""
        entry_id = self.next_entry_id
        self.next_entry_id += 1

        # Convert input to stored format
        entry_data = entry.model_dump()
        entry_data['id'] = entry_id

        # Create the appropriate stored entry type
        stored_entry = self._create_stored_entry(entry_data, entry.label)
        # Store the entry
        self.entries[entry_id] = stored_entry

        # Track name and abbreviation
        self.names_by_label[entry.label].add(entry.name.casefold())
        if entry.abbreviation:
            self.abbreviations_by_label[entry.label].add(entry.abbreviation.casefold())

        return stored_entry

    def _create_stored_entry(self, entry_data: dict, label: str) -> OntologyEntryStored:
        """Create appropriate stored entry subclass based on label."""
        # Map labels to classes
        label_to_class = {
            OntologyEntryLabel.SUBJECT: SubjectStored,
            OntologyEntryLabel.TRAIT: TraitStored,
            OntologyEntryLabel.VARIABLE: VariableStored,
            OntologyEntryLabel.SCALE: ScaleStored,
            OntologyEntryLabel.TERM: TermStored,
            OntologyEntryLabel.OBSERVATION_METHOD: ObservationMethodStored,
            OntologyEntryLabel.CONDITION: ConditionStored,
            OntologyEntryLabel.FACTOR: FactorStored,
            OntologyEntryLabel.EVENT: EventTypeStored,
            OntologyEntryLabel.CATEGORY: ScaleCategoryStored,
            OntologyEntryLabel.CONTROL_METHOD: ControlMethodStored,
            OntologyEntryLabel.LOCATION_TYPE: LocationTypeStored,
            OntologyEntryLabel.LAYOUT_TYPE: LayoutTypeStored,
            OntologyEntryLabel.DESIGN: DesignStored,
            OntologyEntryLabel.ROLE: RoleStored,
            OntologyEntryLabel.TITLE: TitleStored,
        }
        entry_class = label_to_class.get(OntologyEntryLabel(label), OntologyEntryStored)
        return entry_class(**entry_data)

    async def get_entry(
            self,
            entry_id: int = None,
            name:str = None,
            label:str = None,
            as_output:bool = False
    ) -> OntologyEntryStored|None:
        """Retrieve an ontology entry by ID."""
        if entry_id is not None:
            entry = self.entries.get(entry_id)
        else:
            for entry in self.entries.values():
                if entry.name.casefold() == name.casefold() and entry.label == label:
                    break
            else:
                entry = None
        if entry is None:
            return None
        elif not as_output:
            return entry
        else:
            raise NotImplementedError

    async def update_entry(self, entry: OntologyEntryStored) -> None:
        """Update an existing ontology entry."""
        if entry.id not in self.entries:
            raise ValueError(f"Entry {entry.id} does not exist")

        # Update name tracking if name changed
        old_entry = self.entries[entry.id]
        if old_entry.name.casefold() != entry.name.casefold():
            self.names_by_label[entry.label].discard(old_entry.name.casefold())
            self.names_by_label[entry.label].add(entry.name.casefold())

        # Update abbreviation tracking if changed
        if old_entry.abbreviation != entry.abbreviation:
            if old_entry.abbreviation:
                self.abbreviations_by_label[entry.label].discard(old_entry.abbreviation.casefold())
            if entry.abbreviation:
                self.abbreviations_by_label[entry.label].add(entry.abbreviation.casefold())

        self.entries[entry.id] = entry

    async def create_relationship(self, relationship: OntologyRelationshipBase) -> OntologyRelationshipBase:
        """Create a new relationship between entries."""
        rel_id = self.next_relationship_id
        self.next_relationship_id += 1
        relationship.id = rel_id
        self.relationships[relationship.id] = relationship
        return relationship

    async def update_relationship(self, relationship: OntologyRelationshipBase) -> None:
        """Update attributes of an existing relationship."""
        self.relationships[relationship.id] = relationship

    async def get_entries(
            self,
            version: Version|None = None,
            phases: List[LifecyclePhase] | None = None,
            entry_ids: List[int] = None,
            labels: List[OntologyEntryLabel]|None = None,
            names: List[str]|None = None,
            as_output: bool = False,
    ) -> AsyncGenerator[OntologyEntryStored | OntologyEntryOutput, None]:
        """Retrieve ontology entries with filtering."""
        for entry in self.entries.values():
            # Apply filters
            if labels and entry.label not in labels:
                continue
            if names and entry.name not in names:
                continue
            # Note: version and phases filtering would require more complex logic
            # in a real implementation, but for tests we can keep it simple

            yield entry

    async def get_relationships(
            self,
            version: Version | None = None,
            phases: List[LifecyclePhase] | None = None,
            labels: List[OntologyRelationshipLabel] | None = None,
            entry_ids: List[int] = None,
            source_ids: List[int] = None,
            target_ids: List[int] = None

    ) -> AsyncGenerator[OntologyEntryStored | OntologyEntryOutput, None]:
        """Retrieve ontology relationships with filtering."""
        for rel in self.relationships.values():
            # Apply filters
            if labels and rel.label not in labels:
                continue
            if entry_ids and not (rel.source_id in entry_ids or rel.target_id in entry_ids):
                continue
            if source_ids and rel.source_id not in source_ids:
                continue
            if target_ids and rel.target_id not in target_ids:
                continue
            # Note: version and phases filtering would require more complex logic
            # in a real implementation, but for tests we can keep it simple
            yield rel

    async def add_scale_categories(
            self,
            scale_id: int,
            category_data: List[Dict[str, Any]]
    ) -> None:
        """Add categories to a scale with optional ranking."""
        for cat_data in category_data:
            category_id = cat_data['category_id']
            rank = cat_data.get('rank')
            self.scale_categories[scale_id].append((category_id, rank))

    async def get_entry_lifecycles(self, entry_ids: List[int]) -> Dict[int, EntryLifecycle]:
        return self.entry_lifecycles

    # Lifecycle persistence
    async def save_entry_lifecycles(self, lifecycles: Dict[int, EntryLifecycle], user_id: int = None) -> None:
        """Save entry lifecycles to storage."""
        self.entry_lifecycles.update(lifecycles)

    async def activate_drafts(self, version: Version):
        for lifecycle in self.entry_lifecycles.values():
            if lifecycle.current_phase == LifecyclePhase.DRAFT:
                lifecycle.set_version_activated(version)

    async def remove_deprecated(self, version: Version):
        for lifecycle in self.entry_lifecycles.values():
            if lifecycle.current_phase == LifecyclePhase.DEPRECATED:
                lifecycle.set_version_removed(version)

    async def get_relationship_lifecycles(self, relationship_keys: List[int]) -> Dict[int, RelationshipLifecycle]:
        return self.relationship_lifecycles

    async def save_relationship_lifecycles(
            self,
            lifecycles: Dict[int, RelationshipLifecycle],
            user_id: int = None
    ) -> None:
        """Save relationship lifecycles to storage."""
        self.relationship_lifecycles.update(lifecycles)

    async def load_entry_lifecycles(
            self,
            entry_ids: Optional[Set[int]] = None
    ) -> Dict[int, EntryLifecycle]:
        """Load entry lifecycles from storage."""
        if entry_ids is None:
            return self.entry_lifecycles.copy()
        return {eid: lifecycle for eid, lifecycle in self.entry_lifecycles.items() if eid in entry_ids}

    async def load_relationship_lifecycles(
            self,
            relationship_keys: Optional[Set[int]] = None
    ) -> Dict[int, RelationshipLifecycle]:
        """Load relationship lifecycles from storage."""
        if relationship_keys is None:
            return self.relationship_lifecycles.copy()
        return {key: lifecycle for key, lifecycle in self.relationship_lifecycles.items()
                if key in relationship_keys}

    # Validation query methods
    async def name_in_use(
            self,
            label: str,
            name: str,
            exclude_id: int = None
    ) -> bool:
        """Check if name is already in use for a specific entry type."""
        name_lower = name.casefold()

        # If excluding an ID, check if that entry has this name
        if exclude_id and exclude_id in self.entries:
            excluded_entry = self.entries[exclude_id]
            if (excluded_entry.label == label and
                    excluded_entry.name.casefold() == name_lower):
                # The name belongs to the excluded entry, so it's available for update
                return False

        return name_lower in self.names_by_label[label]

    async def abbreviation_in_use(
            self,
            label: str,
            abbreviation: str,
            exclude_id: int = None
    ) -> bool:
        """Check if abbreviation is already in use for a specific entry type."""
        abbr_lower = abbreviation.casefold()

        # If excluding an ID, check if that entry has this abbreviation
        if exclude_id and exclude_id in self.entries:
            excluded_entry = self.entries[exclude_id]
            if (excluded_entry.label == label and
                    excluded_entry.abbreviation and
                    excluded_entry.abbreviation.casefold() == abbr_lower):
                # The abbreviation belongs to the excluded entry, so it's available for update
                return False

        return abbr_lower in self.abbreviations_by_label[label]

    async def entries_exist(self, entry_ids: List[int]) -> Dict[int, bool]:
        """Batch check if entries exist and are in active lifecycle phase."""
        result = {}
        for entry_id in entry_ids:
            exists = entry_id in self.entries
            result[entry_id] = exists
        return result

    async def entries_exist_for_label(self, entry_ids: List[int], label: str) -> Dict[int, bool]:
        """Batch check if entries exist and are in active lifecycle phase."""
        result = {}
        for entry_id in entry_ids:
            exists = entry_id in self.entries and self.entries.get(entry_id).label == label
            result[entry_id] = exists
        return result

    async def get_entry_types(self, entry_ids: List[int]) -> Dict[int, str]:
        """Get the types/labels of multiple entries."""
        return {eid: self.entries[eid].label for eid in entry_ids if eid in self.entries}

    async def relationship_exists(
            self,
            source_id: int,
            sink_id: int,
            label: OntologyRelationshipLabel
    ) -> bool:
        """Check if a specific relationship already exists."""
        for rel in self.relationships.values():
            if rel.source_id == source_id and rel.target_id == sink_id and rel.label == label:
                return True
        return False

    async def has_path_between_entries(
            self,
            source_id: int,
            target_id: int,
            relationship_type: OntologyRelationshipLabel
    ) -> bool:
        """Check if there's a path between two entries (for cycle detection)."""
        # Simple implementation using depth-first search
        if source_id == target_id:
            return True

        visited = set()
        stack = [source_id]

        while stack:
            current_id = stack.pop()
            if current_id in visited:
                continue
            visited.add(current_id)

            # Find all outgoing relationships from current node
            for rel in self.relationships.values():
                if rel.source_id == current_id:
                    if relationship_type is None or rel.label == relationship_type:
                        if rel.target_id == target_id:
                            return True
                        if rel.target_id not in visited:
                            stack.append(rel.target_id)
        return False

    async def get_entry_dependencies(self, entry_id: int) -> List[int]:
        """Get all entries that depend on this entry (incoming relationships)."""
        dependencies = []
        for src, sink, label in self.relationships.keys():
            if sink == entry_id:
                dependencies.append(src)
        return dependencies

    async def get_scale_categories_with_ranks(self, scale_id: int) -> List[Tuple[int, Optional[int]]]:
        """Get categories for a scale with their ranks."""
        return self.scale_categories.get(scale_id, [])

    async def get_current_version(self) -> Version|None:
        if not self.commit_history:
            return Version()
        return max(commit.version for commit in self.commit_history)

    async def _commit_version(self, user_id: int, commit: OntologyCommit):
        """Save version with commit metadata."""
        self.commits[commit.version] = commit
        self.commit_history.append(commit)
        # Sort history by version for consistency
        self.commit_history.sort(key=lambda c: (c.version.major, c.version.minor, c.version.patch))

    async def get_commits(self, version_min: Version = None, version_max: Version = None) -> AsyncGenerator[OntologyCommit, None]:
        if version_min is None:
            version_min = Version.from_packed(0)
        if version_max is None:
            version_max = self.get_current_version()
        for version, commit in self.commits.items():
            if version_min <= version <= version_max:
                yield commit

    async def get_commit_history(self, limit: int = 10) -> AsyncGenerator[OntologyCommit, None]:
        """Get version history ordered by commit time."""
        for commit in self.commit_history[-limit:] if limit > 0 else self.commit_history:
            yield commit