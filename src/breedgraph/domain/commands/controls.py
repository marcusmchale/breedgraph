from .base import Command
from src.breedgraph.domain.model.controls import ControlledModelLabel, ReadRelease

from typing import List

class SetControls(Command):
    agent_id: int

    entity_ids: List[int]
    entity_label: ControlledModelLabel
    release: ReadRelease


