from ariadne import ScalarType, EnumType
from numpy import datetime64
from datetime import datetime

from .registry import graphql_resolvers
from src.breedgraph.domain.model.organisations import Access
from src.breedgraph.domain.model.controls import ReadRelease
from src.breedgraph.domain.model.ontology import VersionChange, OntologyEntryLabel


# Import query and mutation objects (this triggers all resolver registration)
from .queries import graphql_query
from .mutations import graphql_mutation

# Create and register datetime scalar
datetime_scalar = ScalarType("DateTime")

@datetime_scalar.value_parser
def parse_datetime(value):
    return datetime64(value)

@datetime_scalar.serializer
def serialize_datetime(value):
    if isinstance(value, datetime64):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value

graphql_resolvers.register_scalars(datetime_scalar)

# Register enums
graphql_resolvers.register_enums(EnumType("ReadRelease", ReadRelease))
graphql_resolvers.register_enums(EnumType("VersionChange", VersionChange))
graphql_resolvers.register_enums(EnumType("Access", Access))
graphql_resolvers.register_enums(EnumType("OntologyEntryLabel", OntologyEntryLabel))

# Export only what's needed
__all__ = ['graphql_query', 'graphql_mutation', 'datetime_scalar', 'graphql_resolvers']