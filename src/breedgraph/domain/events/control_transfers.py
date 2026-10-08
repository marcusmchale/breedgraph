from .base import Event


class ControlTransferOffered(Event):
    transfer_id: int
    recipient_team: int
    offered_by: int
    entity_count: int
