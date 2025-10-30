from dataclasses import dataclass, asdict
from typing import List
from src.breedgraph.domain.commands import Command
from src.breedgraph.domain.model.time_descriptors import PyDT64
from src.breedgraph.domain.model.germplasm import GermplasmInput, GermplasmRelationship, Reproduction, GermplasmSourceType

from typing import Dict, Any

@dataclass
class GermplasmRelationshipBase:
    source_type: GermplasmSourceType = GermplasmSourceType.UNKNOWN
    description: str | None = None

    def model_dump(self) -> Dict[str, Any]:
        dump = asdict(self)
        dump['source_type'] = dump['source_type'].value
        return dump

    def __post_init__(self):
        self.source_type = GermplasmSourceType(self.source_type)

@dataclass
class GermplasmSourceRelationship(GermplasmRelationshipBase):
    source_id: int = None

@dataclass
class GermplasmSinkRelationship(GermplasmRelationshipBase):
    sink_id: int = None

class CreateGermplasm(Command):
    agent_id: int

    name: str = ''
    description: str | None = None
    synonyms: List[str] | None = None

    author_ids: List[int] | None = None # internal person ID
    reference_ids: List[int] | None = None  # internal reference ID

    origin_id: int | None = None  # internal location
    time: PyDT64|None = None

    reproduction: Reproduction | None = None
    control_method_ids: List[int] | None = None

    sources: List[GermplasmSourceRelationship] | None = None
    sinks: List[GermplasmSinkRelationship] | None = None

class UpdateGermplasm(CreateGermplasm):
    agent_id: int

    id: int
    name: str | None = None

class DeleteGermplasm(Command):
    agent_id: int

    id: int
