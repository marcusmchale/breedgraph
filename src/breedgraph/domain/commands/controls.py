from .base import Command
from breedgraph.domain.model.controls import ControlledModelLabel, ReadRelease
from breedgraph.domain.model.control_transfers import ControlScope

from typing import List

class SetRelease(Command):
    agent_id: int

    # the entities, or a scope
    entity_ids: List[int] | None = None
    entity_label: ControlledModelLabel | None = None
    scope: ControlScope | None = None
    release: ReadRelease
