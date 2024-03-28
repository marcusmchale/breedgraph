from ariadne import (
    QueryType,
    MutationType
)

graphql_query = QueryType()
graphql_mutation = MutationType()

from . import resolvers
