from enum import Enum

class SubmissionStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class SubmissionKeys(Enum):
    AGENT = "agent"
    DATA = "data"
    DATASET_ID = "dataset_id"
    FILE_ID = "file_id"
    STATUS = "status"
    ERRORS = "errors"
    ITEM_ERRORS = "item_errors"

