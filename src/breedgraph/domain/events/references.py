from .base import Event

class UploadFailed(Event):
    user_id: int
    uuid: str
    reference_id: int

class UploadCompleted(Event):
    user_id: int
    uuid: str
    reference_id: int
    file_size: int
    file_hash: str

class FileReferenceDeleted(Event):
    uuid: str
