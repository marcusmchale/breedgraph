from .base import Command

class RequestFileRestore(Command):
    agent_id: int
    file_id: str


class RemoveUnusedFileReferences(Command):
    """
    Remove the file references that nothing cites, and their files, once they have been found unused, and not
    written, for UNUSED_REFERENCE_RETENTION_DAYS
    """


class TriggerFileRetentionPolicy(Command):
    """
    Trigger pruning large files that have not been accessed recently from the local machine
    """
