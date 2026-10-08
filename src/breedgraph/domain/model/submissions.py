from enum import Enum

class SubmissionStatus(Enum):
    PENDING = "pending"
    QUEUED = "queued"  # analysis awaiting a worker
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class SubmissionKeys(Enum):
    AGENT = "agent"
    DATA = "data"
    ANALYSIS = "analysis"
    RESULT = "result"
    DATASET_ID = "dataset_id"
    FILE_ID = "file_id"
    STATUS = "status"
    ERRORS = "errors"
    WARNINGS = "warnings"
    ITEM_ERRORS = "item_errors"
    JOB = "job"  # analysis job payload, while queued or leased
    JOB_WARNINGS = "job_warnings"  # warnings from analysis preparation, written with the final messages
    LEASE = "lease"  # token of the current analysis job lease

class ArchiveKeys(Enum):
    ARCHIVE = "archive" # copy from webserver to archive
    RETRIEVE = "retrieve"  # copy from archive back to webserver
    STORE = "store" # keep local copy on webserver, has expiry
    DELETE = "delete"  # delete permanently

