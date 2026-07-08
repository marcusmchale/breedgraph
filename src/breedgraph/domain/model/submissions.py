from enum import Enum

class SubmissionStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class SubmissionKeys(Enum):
    AGENT = "agent"
    DATA = "data"
    ANALYSIS = '"analysis'
    RESULT = "result"
    DATASET_ID = "dataset_id"
    FILE_ID = "file_id"
    STATUS = "status"
    ERRORS = "errors"
    ITEM_ERRORS = "item_errors"

class ArchiveKeys(Enum):
    ARCHIVE = "archive" # copy from webserver to archive
    RETRIEVE = "retrieve"  # copy from archive back to webserver
    STORE = "store" # keep local copy on webserver, has expiry
    DELETE = "delete"  # delete permanently

