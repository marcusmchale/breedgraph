from enum import Enum
from functools import lru_cache
from src.breedgraph.domain.model.base import EnumLabel

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
    MEASUREMENT = "MEASUREMENT"
    COUNTING = "COUNTING"
    ESTIMATION = "ESTIMATION"
    COMPUTATION = "COMPUTATION"
    PREDICTION = "PREDICTION"
    DESCRIPTION = "DESCRIPTION"
    CLASSIFICATION = "CLASSIFICATION"

class ControlMethodType(str, Enum):
    ENVIRONMENTAL = "ENVIRONMENTAL"  # light,  temperature, humididty etc.
    NUTRITIONAL = "NUTRITIONAL"  # fertilizer etc
    CHEMICAL = "CHEMICAL" # herbicides, hormones etc.
    BIOLOGICAL = "BIOLOGICAL" # microbial treatments etc.
    MANAGEMENT = "MANAGEMENT" # management of planting, pruning etc

class ScaleType(str, Enum):
    DATETIME = "DATE"
    DURATION = "DURATION"
    NUMERICAL = "NUMERICAL"
    TEXT = "TEXT"
    NOMINAL = "NOMINAL"  # should have categories
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