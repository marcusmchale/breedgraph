from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
from enum import Enum


class ArchiveState(Enum):
    """State of file relative to archive server"""
    ARCHIVAL_PENDING = "archival_pending"  # waiting to be sent to archive
    ARCHIVING = "archiving"  # currently being transferred to archive
    ARCHIVED = "archived"  # successfully on archive server
    ARCHIVAL_FAILED = "archival_failed"  # archival attempts exhausted

    RETRIEVAL_PENDING = "retrieval_pending"  # queued to be retrieved from archive
    RETRIEVING = "retrieving"  # currently being transferred from archive, when done state reverts to ARCHIVED
    RETRIEVED = "retrieved" # successfully retrieved, this should revert to ARCHIVED with local_state = LOCAL
    RETRIEVAL_FAILED = "retrieve_failed"  # retrieval attempts exhausted

    DELETION_PENDING = "deletion_pending"  # marked for deletion from the archive
    DELETING = "deleting" # currently being deleted from the archive
    DELETED = "deleted" # successfully removed from the archival server,
    DELETION_FAILED = "deletion_failed" # deletion failed on the archival server

class LocalState(Enum):
    """State of file relative to web server local storage"""
    LOCAL = "local"  # file exists locally
    EXPIRED = "expired"  # local copy has been deleted (but may be on archive)


@dataclass
class FileArchivalRecord:
    """Tracks archival state for large files

    This is a service-layer concern separate from the domain model.
    It tracks infrastructure state for file archival operations.
    """
    file_id: str  # UUID used as filename in file storage, unique identifier
    file_size: int  # size in bytes
    file_hash: str  # SHA256 hash for integrity verification
    last_accessed: datetime  # when this file was last accessed (for pruning of local files)

    # State tracking
    archive_state: ArchiveState = ArchiveState.ARCHIVAL_PENDING
    local_state: LocalState = LocalState.LOCAL
    local_completion: int = 0  # percentage of the total file size for the local file

    # Attempt tracking (infer which operation from state)
    attempts: int = 0
    last_attempt_at: Optional[datetime] = None

    # User tracking for notifications
    requested_by: List[int] = field(default_factory=list)  # users who have requested retrieval

@dataclass
class FileArchivalUpdate:
    archive_state: ArchiveState
