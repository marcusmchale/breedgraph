from ariadne import ObjectType
from ..registry import graphql_resolvers

# Create and register the main query object
graphql_query = ObjectType("Query")
graphql_resolvers.register_query_resolvers(graphql_query)

# Import ALL query modules to register their field resolvers
# These imports need to happen AFTER graphql_query is created
from . import ontology
from . import organisations
from . import regions
from . import arrangements
from . import blocks
from . import datasets
from . import programs
from . import controls
from . import accounts
from . import germplasm

# Export only the main query object
__all__ = ['graphql_query']