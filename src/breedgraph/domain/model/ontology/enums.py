from enum import Enum, IntEnum

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

class ScaleType(str, Enum):
    DATETIME = "DATE"
    DURATION = "DURATION"
    NUMERICAL = "NUMERICAL"
    TEXT = "TEXT"
    NOMINAL = "NOMINAL"  # should have categories
    ORDINAL = "ORDINAL"  # should have categories
    GERMPLASM = "GERMPLASM" # Categories are from Germplasm

class OntologyRelationshipLabel(str, Enum):
    RELATES_TO = 'RELATES_TO' # a generic directed relationship between entries
    # To define scale categories
    HAS_CATEGORY = 'HAS_CATEGORY' # Scale -> Category
    # To define unit subjects (see block outside ontology)
    OF_SUBJECT = 'OF_SUBJECT' # Unit -> Subject
    # To define subject traits/conditions/exposures
    #  - we prefer outgoing edges from subject in the ontology as subject has a lot of income edges from units
    HAS_TRAIT = 'HAS_TRAIT'  # Subject -> Trait
    HAS_CONDITION = 'HAS_CONDITION'  # Subject -> Condition
    HAS_EXPOSURE = 'HAS_EXPOSURE'  # Subject -> Exposure
    # Similarly, Variable/Prameter and EventType have a lot of incoming edges from StudyTerms
    # so prefer outgoing edges from these
    DESCRIBES_TRAIT = 'DESCRIBES_TRAIT' # Variable -> Trait
    DESCRIBES_CONDITION = 'DESCRIBES_CONDITION'  # Parameter -> Condition
    DESCRIBES_EXPOSURE = 'DESCRIBES_EXPOSURE' # EventType -> Exposure
    USES_METHOD = 'USES_METHOD' # Variable/Parameter/EventEntry -> Method
    USES_SCALE = 'USES_SCALE' # Variable/Parameter/EventEntry -> Scale


class VersionChange(IntEnum):
    MAJOR = 0
    MINOR = 1
    PATCH = 2
