from ariadne import (
    make_executable_schema,
    load_schema_from_path,
    snake_case_fallback_resolvers,
    EnumType
)
from src.dbtools.domain.model.accounts import AffiliationLevel
from ariadne import QueryType, MutationType

#  map enums for gql
affiliation_level = EnumType("AffiliationLevel", AffiliationLevel)

graphql_query = QueryType()
graphql_mutation = MutationType()

from . import resolvers  # need to import these here as using decorators

# to update the query and mutation instances

# create the schema instance for use in the graphql route
graphql_schema = make_executable_schema(
    load_schema_from_path("."),
    graphql_query,
    graphql_mutation,
    snake_case_fallback_resolvers,
    affiliation_level
)
