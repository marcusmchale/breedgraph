from enum import Enum
from functools import lru_cache
from breedgraph.domain.model.base import EnumLabel

class LifecyclePhase(Enum):
    """Enumeration of lifecycle phases for ontology entries and relationships."""
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    REMOVED = "removed"

class AxisType(str, Enum):
    """
    Text values with no implied directional relationship
    e.g. Facility: "Growth Facility A"
    """
    NOMINAL = "NOMINAL"
    """
    Text values that convey a sequence but no implied distance 
    e.g. Row: "A", plant: "1"
    """
    ORDINAL = "ORDINAL"
    """
    Numeric values that convey distance to a common origin but do not conform to the requirements of Cartesian coordinates.
    e.g curvilinear spaces, different scales among axes, etc.
    e.g. Row: "1.0", plant: "2.5"
    """
    COORDINATE = "COORDINATE"
    """
    All Cartesian axes for a given Layout must:
     - be pair-wise perpendicular,
     - have a common origin,
     - and common unit of length (metres).
    This allows distance calculations.
    Integer values are coerced to floating point numbers.
    e.g. Row: "1.0", plant: "2.5"    
    """
    CARTESIAN = "CARTESIAN"

class ObservationMethodType(str, Enum):
    """Broad category describing how the value of a Variable is obtained."""

    MEASUREMENT = "MEASUREMENT"
    """Value obtained by direct measurement using an instrument or defined procedure."""

    COUNTING = "COUNTING"
    """Value obtained by enumerating discrete entities, occurrences, or features."""

    ESTIMATION = "ESTIMATION"
    """Value obtained by estimating a characteristic, typically when direct measurement
    is impractical or when a defined visual or expert assessment is used."""

    COMPUTATION = "COMPUTATION"
    """Value derived by applying a defined calculation or algorithm to observed or
    otherwise available data."""

    PREDICTION = "PREDICTION"
    """Value inferred or predicted using a model, statistical method, or other
    predictive approach."""

    DESCRIPTION = "DESCRIPTION"
    """Value recorded as a descriptive observation, typically using free text or
    a defined descriptive vocabulary."""

    CLASSIFICATION = "CLASSIFICATION"
    """Value assigned by categorising an observation according to a defined
    classification scheme or set of classes."""


class ControlMethodType(str, Enum):
    """Broad category describing the domain of a ControlMethod.

    This is a general classification label for organising and filtering control
    methods. It is not intended to provide an exhaustive or mutually exclusive
    taxonomy of control methods.
    """

    ENVIRONMENTAL = "ENVIRONMENTAL"
    """Control or manipulation of environmental conditions or exposures, such as
    light, temperature, humidity, or atmospheric conditions."""

    NUTRITIONAL = "NUTRITIONAL"
    """Control or manipulation of nutritional conditions, including the supply,
    composition, or availability of nutrients."""

    CHEMICAL = "CHEMICAL"
    """Control involving the application or manipulation of chemical agents,
    substances, or treatments, including herbicides, hormones, and growth
    regulators."""

    BIOLOGICAL = "BIOLOGICAL"
    """Control involving biological agents, organisms, or biological interactions,
    including microbial or other biological treatments."""

    MANAGEMENT = "MANAGEMENT"
    """Control through agricultural, horticultural, experimental, or other
    management practices, such as planting, sowing, pruning, irrigation,
    or harvesting."""

    GENETIC = "GENETIC"
    """Control or manipulation of genetic material or genetic relationships,
    including crossing, selection, propagation, and other germplasm-management
    operations."""

class ScaleType(str, Enum):
    DATE = "DATE"
    DURATION = "DURATION"
    NUMERICAL = "NUMERICAL"
    TEXT = "TEXT"
    NOMINAL = "NOMINAL"  # should have categories, Boolean values are represented as nominal scales (e.g. Yes/No, Present/Absent)
    ORDINAL = "ORDINAL"  # should have categories
    COMPLEX = "COMPLEX" # Allows for hdf5, json, sparse matrixes, tables, trees etc. should define a schema

class OntologyEntryLabel(EnumLabel):
    TERM = "Term"
    SUBJECT = "Subject"
    SCALE = "Scale"
    CATEGORY = "Category"
    OBSERVATION_METHOD = "ObservationMethod"
    TRAIT = "Trait"
    VARIABLE = "Variable"
    CONTROL_METHOD = "ControlMethod"
    CONDITION = "Condition"
    FACTOR = "Factor"
    EVENT = "Event"
    LOCATION_TYPE = "LocationType"
    LAYOUT_TYPE = "LayoutType"
    DESIGN = "Design"
    ROLE = "Role"
    TITLE = "Title"

    @classmethod
    @lru_cache(maxsize=1)
    def _enum_to_plural_map(cls) -> dict[str, str]:
        return {
            cls.TERM: "Terms",
            cls.SUBJECT: "Subjects",
            cls.SCALE: "Scales",
            cls.CATEGORY: "Categories",
            cls.OBSERVATION_METHOD: "ObservationMethods",
            cls.TRAIT: "Traits",
            cls.VARIABLE: "Variables",
            cls.CONTROL_METHOD: "ControlMethods",
            cls.CONDITION: "Conditions",
            cls.FACTOR: "Factors",
            cls.EVENT: "EventTypes",
            cls.LOCATION_TYPE: "LocationTypes",
            cls.LAYOUT_TYPE: "LayoutTypes",
            cls.DESIGN: "Designs",
            cls.ROLE: "Roles",
            cls.TITLE: "Titles"
        }

    @property
    def label(self):
        return self.value

    @property
    def plural(self):
        return self._enum_to_plural_map()[self]

class OntologyRelationshipLabel(str, Enum):
    PARENT_OF = 'ParentOf' # Any => SAME_TYPE
    HAS_TERM = 'HasTerm' # Any => Term
    HAS_CATEGORY = 'HasCategory' # Scale -> Category
    DESCRIBES_SUBJECT = 'DescribesSubject' # Trait/Condition -> Subject
    DESCRIBES_TRAIT = 'DescribesTrait' # Variable -> Trait
    DESCRIBES_CONDITION = 'DescribesCondition'  # Factor -> Condition
    USES_OBSERVATION_METHOD = 'UsesObservationMethod'  # Variable -> ObservationMethod
    USES_CONTROL_METHOD = 'UsesControlMethod' # Factor -> ControlMethod
    USES_SCALE = 'UsesScale' # Variable/Factor -> Scale
    DESCRIBES_FACTOR = 'DescribesFactor' # EventType -> Factor
    DESCRIBES_VARIABLE = 'DescribesVariable' # EventType -> Variable

class VersionChange(str, Enum):
    MAJOR = 'MAJOR'
    MINOR = 'MINOR'
    PATCH = 'PATCH'