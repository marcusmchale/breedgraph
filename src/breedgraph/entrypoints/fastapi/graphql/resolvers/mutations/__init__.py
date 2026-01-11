from ariadne import ObjectType
from ..registry import graphql_resolvers

# Create and register the main mutation object
graphql_mutation = ObjectType("Mutation")
graphql_resolvers.register_mutation_resolvers(graphql_mutation)

# Import ALL mutation modules to register their field resolvers
# These imports need to happen AFTER graphql_mutation is created
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
from . import references

# Export only the main mutation object
__all__ = ['graphql_mutation']