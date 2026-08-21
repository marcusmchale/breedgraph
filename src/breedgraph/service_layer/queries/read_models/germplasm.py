from dataclasses import dataclass, InitVar

from numpy import datetime64

from breedgraph.domain.model.germplasm import Reproduction, GermplasmSourceType


@dataclass(frozen=True)
class GermplasmRelationshipOutput:
    source_id: int
    sink_id: int

    source_type: GermplasmSourceType = GermplasmSourceType.UNKNOWN
    description: str| None = None

@dataclass(frozen=True)
class GermplasmEntryOutput:
    id: int

    name: str
    description: str| None = None
    synonyms: tuple[str, ...] = ()

    authors: tuple[int, ...] = ()
    references: tuple[int, ...] = ()

    origin: int | None = None
    time: datetime64 | None = None

    reproduction: Reproduction | None = None
    control_methods: tuple[int, ...] = ()

    sources: tuple[GermplasmRelationshipOutput, ...] = ()
    sinks: tuple[GermplasmRelationshipOutput, ...] = ()