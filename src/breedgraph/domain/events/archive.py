from .base import Event

class ArchivalFailed(Event):
    """Archival failed"""
    file_id: str
    error_message: str

class RetrievalSucceeded(Event):
    """File successfully retrieved from archive"""
    file_id: str

class RetrievalFailed(Event):
    """Retrieval failed with attempt limit exceeded """
    file_id: str
    error_message: str
