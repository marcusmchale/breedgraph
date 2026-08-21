from abc import ABC
from dataclasses import dataclass, asdict, field
from enum import Enum
from numpy import datetime64

from breedgraph.domain.model.ontology import (
    Version,
    LifecyclePhase,
    OntologyEntryLabel, OntologyRelationshipLabel,
    ObservationMethodType, ControlMethodType,
    ScaleType,
    AxisType
)

from typing import ClassVar, Dict, Any

class OntologyViewMode(Enum):
    PUBLISHED = "PUBLISHED"
    EDITORIAL = "EDITORIAL"
    REFERENTIAL = "REFERENTIAL"

@dataclass(frozen=True)
class OntologyRelationshipOutput:
    label: OntologyRelationshipLabel

    id: int
    version: Version
    view: OntologyViewMode

    phase: LifecyclePhase

    source_id: int
    target_id: int
    rank: int | None = None

    def model_dump(self):
        dump = asdict(self)
        dump['label'] = self.label.value
        return dump


@dataclass(frozen=True)
class OntologyEntryOutput(ABC):
    label: ClassVar[OntologyEntryLabel]

    id: int
    version: Version
    view: OntologyViewMode

    phase: LifecyclePhase

    name: str = ''
    abbreviation: str | None = None
    description: str | None = None
    
    synonyms: tuple[str, ...] = ()
    authors: tuple[int, ...] = ()
    references: tuple[int, ...] = ()

    parents: tuple[int, ...] = ()
    children: tuple[int, ...] = ()


    @property
    def names(self) -> tuple[str, ...]:
        """Convenience accessor including synonyms and optional abbreviation."""
        return tuple(
            x for x in (self.name, *self.synonyms, self.abbreviation) if x is not None
        )

    @property
    def abbreviation_lower(self) -> str:
        return self.abbreviation.casefold() if self.abbreviation else None

    def model_dump(self) -> Dict[str, Any]:
        dump = asdict(self)
        if 'scale_type' in dump:
            dump['scale_type'] = dump['scale_type'].value
        if 'observation_type' in dump:
            dump['observation_type'] = dump['observation_type'].value
        if 'control_type' in dump:
            dump['control_type'] = dump['control_type'].value
        if 'axes' in dump:
            dump['axes'] = [a.value for a in dump['axes']]
        return dump


@dataclass(frozen=True)
class TermOutput(OntologyEntryOutput):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.TERM

    subjects: tuple[int, ...] = ()
    scales: tuple[int, ...] = ()
    categories: tuple[int, ...] = ()
    observation_methods: tuple[int, ...] = ()
    traits: tuple[int, ...] = ()
    variables: tuple[int, ...] = ()
    control_methods: tuple[int, ...] = ()
    conditions: tuple[int, ...] = ()
    factors: tuple[int, ...] = ()
    events: tuple[int, ...] = ()
    location_types: tuple[int, ...] = ()
    layout_types: tuple[int, ...] = ()
    designs: tuple[int, ...] = ()
    roles: tuple[int, ...] = ()
    titles: tuple[int, ...] = ()

@dataclass(frozen=True)
class LocationTypeOutput(OntologyEntryOutput):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.LOCATION_TYPE
    terms: tuple[int, ...] = ()


@dataclass(frozen=True)
class LayoutTypeOutput(OntologyEntryOutput):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.LAYOUT_TYPE
    terms: tuple[int, ...] = ()

    axes: tuple[AxisType, ...] = ()

@dataclass(frozen=True)
class SubjectOutput(OntologyEntryOutput):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.SUBJECT
    terms: tuple[int, ...] = ()

    traits: tuple[int, ...] = ()
    conditions: tuple[int, ...] = ()

@dataclass(frozen=True)
class CategoryOutput(OntologyEntryOutput):
    label: ClassVar[str] = OntologyEntryLabel.CATEGORY
    terms: tuple[int, ...] = ()

    scales: tuple[int, ...] = ()

@dataclass(frozen=True)
class ScaleOutput(OntologyEntryOutput):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.SCALE
    terms: tuple[int, ...] = ()

    scale_type: ScaleType = ScaleType.TEXT
    categories: tuple[int, ...]|None = None

    variables: tuple[int, ...] = ()
    factors: tuple[int, ...] = ()

@dataclass(frozen=True)
class ControlMethodOutput(OntologyEntryOutput):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.CONTROL_METHOD
    terms: tuple[int, ...] = ()

    control_type: ControlMethodType = ControlMethodType.ENVIRONMENTAL
    factors: tuple[int, ...] = ()

@dataclass(frozen=True)
class ConditionOutput(OntologyEntryOutput):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.CONDITION
    terms: tuple[int, ...] = ()

    subjects: tuple[int, ...] = ()
    factors: tuple[int, ...] = ()

@dataclass(frozen=True)
class FactorOutput(OntologyEntryOutput):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.FACTOR
    terms: tuple[int, ...] = ()

    condition: int = None
    control_method: int = None
    scale: int = None

@dataclass(frozen=True)
class ObservationMethodOutput(OntologyEntryOutput):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.OBSERVATION_METHOD
    terms: tuple[int, ...] = ()

    observation_type: ObservationMethodType = ObservationMethodType.MEASUREMENT
    variables: tuple[int, ...] = ()

@dataclass(frozen=True)
class TraitOutput(OntologyEntryOutput):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.TRAIT
    terms: tuple[int, ...] = ()

    subjects: tuple[int, ...] = ()
    variables: tuple[int, ...] = ()

@dataclass(frozen=True)
class VariableOutput(OntologyEntryOutput):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.VARIABLE
    terms: tuple[int, ...] = ()

    trait: int = None
    observation_method: int = None
    scale: int = None

@dataclass(frozen=True)
class DesignOutput(OntologyEntryOutput):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.DESIGN
    terms: tuple[int, ...] = ()

@dataclass(frozen=True)
class EventOutput(OntologyEntryOutput):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.EVENT
    terms: tuple[int, ...] = ()

    factors: tuple[int, ...] = ()
    variables: tuple[int, ...] = ()

@dataclass(frozen=True)
class RoleOutput(OntologyEntryOutput):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.ROLE
    terms: tuple[int, ...] = ()

@dataclass(frozen=True)
class TitleOutput(OntologyEntryOutput):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.TITLE
    terms: tuple[int, ...] = ()

@dataclass(frozen=True)
class Ontology:
    version: Version
    view: OntologyViewMode

    entries: tuple[OntologyEntryOutput, ...]
    relationships: tuple[OntologyRelationshipOutput, ...]

@dataclass(frozen=True)
class OntologyEntryPatch:
    contributor: int
    time: datetime64
    entryId: int

    attributes: dict|None = None

    references_added: list[int]|None = None
    references_removed: list[int]|None = None
    authors_added: list[int] | None = None
    authors_removed: list[int] | None = None

@dataclass(frozen=True)
class OntologyRelationshipPatch:
    contributor: int
    time: datetime64
    relationshipId: int

    attributes: dict|None = None
