"""
A Variable is a property whose value is established by observation or measurement.

I considered the following reference in designing this model:

    Pietragalla, J.; Valette, L.; Shrestha, R.; Laporte, M.-A.; Hazekamp, T.; Arnaud, E. (2022)
    Guidelines for creating crop-specific Ontology to annotate phenotypic data: version 2.1.
    Alliance Bioversity International and CIAT. 38 p.
    https://hdl.handle.net/10568/110906

In particular the adoption of Trait/Method/Scale (T/M/S) definition for a Variable and
Terms to relate these concepts. Terms can have parent-child relationships to other terms.
T/M/S and Variable have more restricted relationships.

When entering Traits, references to the Plant Trait Ontology should be encouraged.

Note: The "Variable Status" concept from Crop Ontology is to be handled by ontology lifecycle in BreedGraph.

"""
from dataclasses import dataclass, field
from breedgraph.domain.model.ontology.entries import (
    OntologyEntryBase, OntologyEntryInput, OntologyEntryStored
)
from breedgraph.domain.model.ontology.enums import ObservationMethodType, ScaleType, OntologyEntryLabel
from typing import ClassVar, List


@dataclass
class TraitBase(OntologyEntryBase):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.TRAIT

    subjects: List[int] = field(default_factory=list)

@dataclass
class TraitInput(TraitBase, OntologyEntryInput):
    pass

@dataclass
class TraitStored(TraitBase, OntologyEntryStored):
    pass


@dataclass
class ObservationMethodBase(OntologyEntryBase):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.OBSERVATION_METHOD

    observation_type: ObservationMethodType = ObservationMethodType.MEASUREMENT

@dataclass
class ObservationMethodInput(ObservationMethodBase, OntologyEntryInput):
    pass

@dataclass
class ObservationMethodStored(ObservationMethodBase, OntologyEntryStored):
    pass


@dataclass(frozen=True)
class ScaleCategory:
    """
    A level of a nominal or ordinal scale, not an ontology entry: records hold its name, so names are unique on the
    scale, ignoring case, and its description says what the level means on this scale.
    """
    name: str
    description: str | None = None

    def __post_init__(self):
        object.__setattr__(self, 'name', self.name.strip())
        object.__setattr__(self, 'description', (self.description or '').strip() or None)

    @classmethod
    def from_arrays(cls, names: List[str], descriptions: List[str] | None) -> List['ScaleCategory']:
        """The categories as a scale is stored (OntologyEntryBase.model_dump)"""
        descriptions = descriptions or [''] * len(names)
        return [cls(name, description) for name, description in zip(names, descriptions)]

@dataclass
class ScaleBase(OntologyEntryBase):
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.SCALE
    LOCKED_ATTRIBUTES: ClassVar[tuple[str, ...]] = OntologyEntryBase.LOCKED_ATTRIBUTES + ('categories',)

    scale_type: ScaleType = ScaleType.TEXT
    # in order: the rank of an ordinal scale's levels, the order a nominal scale's are presented in
    categories: List[ScaleCategory] = field(default_factory=list)

    def __post_init__(self):
        self.categories = [c if isinstance(c, ScaleCategory) else ScaleCategory(**c) for c in self.categories or []]

    def validate_categories(self) -> None:
        """Nominal and ordinal scales have categories, with distinct names; other scales have none"""
        if self.scale_type not in (ScaleType.NOMINAL, ScaleType.ORDINAL):
            if self.categories:
                raise ValueError("Categories are only valid for nominal and ordinal scales")
            return
        if not self.categories:
            raise ValueError(f"A {self.scale_type.value.lower()} scale needs categories")
        names = [category.name.casefold() for category in self.categories]
        if not all(names):
            raise ValueError("Category names can't be empty")
        repeated = sorted({category.name for category in self.categories if names.count(category.name.casefold()) > 1})
        if repeated:
            raise ValueError(f"Category names must differ on a scale, ignoring case: {', '.join(repeated)}")

@dataclass
class ScaleInput(ScaleBase, OntologyEntryInput):
    pass

@dataclass
class ScaleStored(ScaleBase, OntologyEntryStored):

    def __post_init__(self):
        super().__post_init__()
        self.scale_type = ScaleType(self.scale_type)

@dataclass
class VariableBase(OntologyEntryBase):  # quantities/qualities that vary and may be observed
    label: ClassVar[OntologyEntryLabel] = OntologyEntryLabel.VARIABLE
    # CropOntology requires name to be <TraitAbbreviation>_<MethodAbbreviation >_< ScaleAbbreviation >
    # makes more sense for this format to be the abbreviation value of the OntologyEntry class

@dataclass
class VariableInput(VariableBase, OntologyEntryInput):
    pass

@dataclass
class VariableStored(VariableBase, OntologyEntryStored):
    pass
