from abc import ABC
from dataclasses import dataclass, asdict, field

from breedgraph.domain.model.ontology import (
    Version,
    LifecyclePhase,
    OntologyEntryLabel, OntologyRelationshipLabel,
    ObservationMethodType, ControlMethodType,
    ScaleType,
    AxisType
)

from typing import ClassVar, Tuple, Dict, Any, List

@dataclass(frozen=True)
class OntologyRelationshipOutput:
    label: OntologyRelationshipLabel

    id: int
    version: Version

    source_id: int
    target_id: int
    phase: LifecyclePhase
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
    draft: bool  # flag for whether draft attributes are included

    name: str = ''
    abbreviation: str | None = None
    description: str | None = None
    
    synonyms: Tuple[str, ...] = ()
    authors: Tuple[int, ...] = ()
    references: Tuple[int, ...] = ()

    parents: Tuple[int, ...] = ()
    children: Tuple[int, ...] = ()

    phase: LifecyclePhase = None

    @property
    def names(self) -> Tuple[str, ...]:
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
        if 'axes' in dump:
            dump['axes'] = [a.value for a in dump['axes']]
        return dump


@dataclass(frozen=True)
class TermOutput(OntologyEntryOutput):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.TERM

    subjects: Tuple[int, ...] = ()
    scales: Tuple[int, ...] = ()
    categories: Tuple[int, ...] = ()
    observation_methods: Tuple[int, ...] = ()
    traits: Tuple[int, ...] = ()
    variables: Tuple[int, ...] = ()
    control_methods: Tuple[int, ...] = ()
    conditions: Tuple[int, ...] = ()
    factors: Tuple[int, ...] = ()
    events: Tuple[int, ...] = ()
    location_types: Tuple[int, ...] = ()
    layout_types: Tuple[int, ...] = ()
    designs: Tuple[int, ...] = ()
    roles: Tuple[int, ...] = ()
    titles: Tuple[int, ...] = ()

@dataclass(frozen=True)
class LocationTypeOutput(OntologyEntryOutput):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.LOCATION_TYPE
    terms: Tuple[int, ...] = ()


@dataclass(frozen=True)
class LayoutTypeOutput(OntologyEntryOutput):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.LAYOUT_TYPE
    terms: Tuple[int, ...] = ()

    axes: Tuple[AxisType, ...] = ()

@dataclass(frozen=True)
class SubjectOutput(OntologyEntryOutput):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.SUBJECT
    terms: Tuple[int, ...] = ()

    traits: Tuple[int, ...] = ()
    conditions: Tuple[int, ...] = ()

@dataclass(frozen=True)
class ScaleCategoryOutput(OntologyEntryOutput):
    label: ClassVar[str] = OntologyEntryLabel.CATEGORY
    terms: Tuple[int, ...] = ()

    scales: Tuple[int, ...] = ()

@dataclass(frozen=True)
class ScaleOutput(OntologyEntryOutput):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.SCALE
    terms: Tuple[int, ...] = ()

    scale_type: ScaleType = ScaleType.TEXT
    categories: Tuple[int, ...]|None = None

    variables: Tuple[int, ...] = ()
    factors: Tuple[int, ...] = ()

@dataclass(frozen=True)
class ControlMethodOutput(OntologyEntryOutput):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.CONTROL_METHOD
    terms: Tuple[int, ...] = ()

    control_type: ControlMethodType = ControlMethodType.ENVIRONMENTAL
    factors: Tuple[int, ...] = ()

@dataclass(frozen=True)
class ConditionOutput(OntologyEntryOutput):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.CONDITION
    terms: Tuple[int, ...] = ()

    subjects: Tuple[int, ...] = ()
    factors: Tuple[int, ...] = ()

@dataclass(frozen=True)
class FactorOutput(OntologyEntryOutput):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.FACTOR
    terms: Tuple[int, ...] = ()

    condition: int = None
    control_method: int = None
    scale: int = None

@dataclass(frozen=True)
class ObservationMethodOutput(OntologyEntryOutput):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.OBSERVATION_METHOD
    terms: Tuple[int, ...] = ()

    observation_type: ObservationMethodType = ObservationMethodType.MEASUREMENT
    variables: Tuple[int, ...] = ()

@dataclass(frozen=True)
class TraitOutput(OntologyEntryOutput):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.TRAIT
    terms: Tuple[int, ...] = ()

    subjects: Tuple[int, ...] = ()
    variables: Tuple[int, ...] = ()

@dataclass(frozen=True)
class VariableOutput(OntologyEntryOutput):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.VARIABLE
    terms: Tuple[int, ...] = ()

    trait: int = None
    observation_method: int = None
    scale: int = None

@dataclass(frozen=True)
class DesignOutput(OntologyEntryOutput):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.DESIGN
    terms: Tuple[int, ...] = ()

@dataclass(frozen=True)
class EventTypeOutput(OntologyEntryOutput):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.EVENT
    terms: Tuple[int, ...] = ()

    factors: Tuple[int, ...] = ()
    variables: Tuple[int, ...] = ()

@dataclass(frozen=True)
class RoleOutput(OntologyEntryOutput):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.ROLE
    terms: Tuple[int, ...] = ()

@dataclass(frozen=True)
class TitleOutput(OntologyEntryOutput):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.TITLE
    terms: Tuple[int, ...] = ()


@dataclass(frozen=True)
class Ontology:
    version: Version
    entries: Tuple[OntologyEntryOutput, ...]
    relationships: Tuple[OntologyRelationshipOutput, ...]