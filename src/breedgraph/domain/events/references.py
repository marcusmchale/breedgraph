from .base import Event

class UploadFailed(Event):
    user_id: int
    uuid: str
    reference_id: int

class UploadCompleted(Event):
    user_id: int
    uuid: str
    reference_id: int

class FileReferenceDeleted(Event):
    uuid: str
