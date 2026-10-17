from .base import Command
from breedgraph.domain.model.controls import ReadRelease
from breedgraph.domain.model.control_transfers import ControlledEntity, ControlScope

from typing import List, Set

class OfferControlTransfer(Command):
    agent_id: int

    # the entities, or a scope
    entities: List[ControlledEntity] | None = None
    scope: ControlScope | None = None
    from_teams: Set[int]
    recipient_team: int
    keep_from_teams: bool = False

    # Used only when the offering user is also an admin of the recipient team,
    # in which case the transfer is accepted immediately.
    to_teams: Set[int] | None = None
    release: ReadRelease = ReadRelease.PRIVATE

class AcceptControlTransfer(Command):
    agent_id: int
    transfer_id: int

    to_teams: Set[int]
    release: ReadRelease = ReadRelease.PRIVATE

class RejectControlTransfer(Command):
    agent_id: int
    transfer_id: int

class CancelControlTransfer(Command):
    agent_id: int
    transfer_id: int

class RenounceControl(Command):
    agent_id: int

    # the entities, or a scope
    entities: List[ControlledEntity] | None = None
    scope: ControlScope | None = None
    team_ids: Set[int]
