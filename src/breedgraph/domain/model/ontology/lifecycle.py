from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple, Self, Dict, ClassVar

from numpy import datetime64

from src.breedgraph.service_layer.tracking.wrappers import asdict
from src.breedgraph.domain.model.time_descriptors import WriteStamp
from src.breedgraph.domain.model.ontology.version import Version
from src.breedgraph.domain.model.ontology.enums import OntologyRelationshipLabel, LifecyclePhase

@dataclass
class LifecycleAuditEntry:
    user_id: int
    lifecycle: LifecyclePhase
    time: datetime64

@dataclass
class BaseLifecycle(ABC):
    """Abstract base class for ontology lifecycle management."""
    version_fields: ClassVar[List['str']] = ['version_drafted', 'version_activated', 'version_deprecated', 'version_removed']

    # Version tracking - stored as full Version objects
    version_drafted: Optional[Version] = None
    version_activated: Optional[Version] = None
    version_deprecated: Optional[Version] = None
    version_removed: Optional[Version] = None

    # Edit history (read only attributes)
    _writestamps: List[WriteStamp] = field(default_factory=list)  # history of changes to the corresponding ontology entry
    _history: List[LifecycleAuditEntry] = field(default_factory=list) # history of the ontology entry lifecycle

    def serialize_versions(self) -> Dict[str, int]:
        """Serialize version data into a nested versions dictionary."""
        versions = {}
        for version_field in self.version_fields:
            version_obj = getattr(self, version_field)
            if version_obj is not None:
                # Remove 'version_' prefix for cleaner nested structure
                clean_field_name = version_field.replace('version_', '')
                versions[clean_field_name] = version_obj.id

        return versions

    @property
    def writestamps(self) -> List[WriteStamp]:
        """Read-only access to writestamps."""
        return self._writestamps.copy()

    @property
    def history(self) -> List[LifecycleAuditEntry]:
        """Read-only access to history."""
        return self._history.copy()

    @property
    def current_phase(self) -> LifecyclePhase:
        """Compute current lifecycle phase based on version states."""
        if self.version_removed is not None:
            return LifecyclePhase.REMOVED
        elif self.version_deprecated is not None:
            return LifecyclePhase.DEPRECATED
        elif self.version_activated is not None:
            return LifecyclePhase.ACTIVE
        elif self.version_drafted is not None:
            return LifecyclePhase.DRAFT
        else:
            # This shouldn't happen in normal operation, but default to draft
            return LifecyclePhase.DRAFT

    def set_version_drafted(self, version: Version) -> None:
        """Set the drafted version."""
        self.version_drafted = version

    def set_version_activated(self, version: Version) -> None:
        """Set the validated version (transition to active)."""
        if self.current_phase != LifecyclePhase.DRAFT:
            raise ValueError(f"Cannot transition to active from {self.current_phase.value}")

        self.version_activated = version

    def set_version_deprecated(self, version: Version) -> None:
        """Set the deprecated version."""
        if self.current_phase != LifecyclePhase.ACTIVE:
            raise ValueError(f"Cannot transition to deprecated from {self.current_phase.value}")

        self.version_deprecated = version

    def set_version_removed(self, version: Version) -> None:
        """Set the removed version."""
        if self.current_phase != LifecyclePhase.DEPRECATED:
            raise ValueError(f"Cannot transition to removed from {self.current_phase.value}")

        self.version_removed = version

    def is_in_phase(self, phase: LifecyclePhase) -> bool:
        """Check if entity is in a specific phase."""
        return self.current_phase == phase

    def model_dump(self):
        dump = asdict(self)
        dump.pop('_writestamps')
        dump.pop('_history')
        # Remove individual version fields from top level
        for version_field in self.version_fields:
            dump.pop(version_field, None)
        # Add nested versions structure
        versions = self.serialize_versions()
        if versions:
            dump['versions'] = versions
        dump['current_phase'] = self.current_phase.name
        return dump

@dataclass
class EntryLifecycle(BaseLifecycle):
    """Domain model for managing the lifecycle of ontology entries."""
    entry_id: int = None

@dataclass
class RelationshipLifecycle(BaseLifecycle):
    """Domain model for managing the lifecycle of ontology relationships."""
    relationship_id: int = None
