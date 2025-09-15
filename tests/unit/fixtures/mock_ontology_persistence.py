from typing import Optional, Dict, List, Set, Tuple, Any, AsyncGenerator
from collections import defaultdict

from src.breedgraph.service_layer.persistence import OntologyPersistenceService
from src.breedgraph.domain.model.ontology import *


class MockOntologyPersistenceService(OntologyPersistenceService):
    """Mock implementation for testing ontology application service."""

    def __init__(self):
        # Storage for entries
        self.entries: Dict[int, OntologyEntryStored] = {}
        self.next_entry_id = 1

        # Storage for relationships
        self.relationships: Dict[OntologyRelationshipBase.key, OntologyRelationshipBase] = {}

        # Storage for lifecycles
        self.entry_lifecycles: Dict[int, EntryLifecycle] = {}
        self.relationship_lifecycles: Dict[Tuple[int, int, OntologyRelationshipLabel], RelationshipLifecycle] = {}

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
            "Subject": SubjectStored,
            "Trait": TraitStored,
            "Variable": VariableStored,
            "Scale": ScaleStored,
            "Term": TermStored,
            "ObservationMethod": ObservationMethodStored,
            "Condition": ConditionStored,
            "Factor": FactorStored,
            "EventType": EventTypeStored,
            "Category": ScaleCategoryStored,
            "ControlMethod": ControlMethodStored,
            "GermplasmMethod": GermplasmMethodStored,
            "LocationType": LocationTypeStored,
            "LayoutType": LayoutTypeStored,
            "Design": DesignStored,
            "Role": RoleStored,
            "Title": TitleStored,
        }
        entry_class = label_to_class.get(label, OntologyEntryStored)
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

    async def create_relationship(self, relationship: OntologyRelationshipBase) -> None:
        """Create a new relationship between entries."""
        self.relationships[relationship.key] = relationship

    async def update_relationship(self, relationship: OntologyRelationshipBase) -> None:
        """Update attributes of an existing relationship."""
        self.relationships[relationship.key] = relationship

    async def get_relationships_by_label(
            self,
            entry_id: int,
            label: OntologyRelationshipLabel = None
    ) ->AsyncGenerator[OntologyRelationshipBase, None]:
        """Get all relationships for an entry, optionally filtered by label."""
        for source_id, sink_id, rel_label in self.relationships.keys():
            # Check if this relationship involves the given entry
            if source_id == entry_id or sink_id == entry_id:
                # If a specific label is requested, filter by it
                if label is None or rel_label == label:
                    yield self.relationships.get((source_id, sink_id, rel_label))

    async def get_entries(
            self,
            version: Version = None,
            phases: List[LifecyclePhase] = None,
            labels: List[str] = None,
            names: List[str] = None,
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

    # Lifecycle persistence
    async def save_entry_lifecycles(self, lifecycles: Dict[int, EntryLifecycle], user_id: int = None) -> None:
        """Save entry lifecycles to storage."""
        self.entry_lifecycles.update(lifecycles)

    async def save_relationship_lifecycles(
            self,
            lifecycles: Dict[Tuple[int, int, OntologyRelationshipLabel], RelationshipLifecycle],
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
            relationship_keys: Optional[Set[Tuple[int, int, OntologyRelationshipLabel]]] = None
    ) -> Dict[Tuple[int, int, OntologyRelationshipLabel], RelationshipLifecycle]:
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
        return (source_id, sink_id, label) in self.relationships

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
            for src, sink, label in self.relationships.keys():
                if src == current_id:
                    if relationship_type is None or label == relationship_type:
                        if sink == target_id:
                            return True
                        if sink not in visited:
                            stack.append(sink)
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
            return None
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