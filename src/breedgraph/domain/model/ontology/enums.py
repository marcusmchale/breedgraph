from enum import Enum

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
    GENETIC = "GENETIC" # germplasm etc
    MANAGEMENT = "MANAGEMENT" # management of planting, pruning etc

class ScaleType(str, Enum):
    DATETIME = "DATE"
    DURATION = "DURATION"
    NUMERICAL = "NUMERICAL"
    TEXT = "TEXT"
    NOMINAL = "NOMINAL"  # should have categories
    ORDINAL = "ORDINAL"  # should have categories
    GERMPLASM = "GERMPLASM" # Categories are from Germplasm

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