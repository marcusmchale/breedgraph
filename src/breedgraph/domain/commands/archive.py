from .base import Command

class RequestFileRestore(Command):
    agent_id: int
    file_id: str


class TriggerFileRetentionPolicy(Command):
    """
    Trigger pruning large files that have not been accessed recently from the local machine
    """
