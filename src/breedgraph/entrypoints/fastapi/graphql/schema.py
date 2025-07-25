from ariadne import (
    EnumType,
    make_executable_schema,
    load_schema_from_path,
    snake_case_fallback_resolvers
)
from src.breedgraph.entrypoints.fastapi.graphql.resolvers import (
    graphql_query,
    graphql_mutation,
    team,
    affiliations,
    affiliation,
    user,
    account,
    ontology_entry,
    location,
    layout,
    unit,
    dataset,
    record,
    datetime_scalar
)

# logging
import logging
logger = logging.getLogger(__name__)

def create_graphql_schema():
    """Create and return the GraphQL schema with all resolvers bound"""
    logger.debug("Building GraphQL schema")
    
    # Map enums for GraphQL if needed
    # access_level = EnumType("AccessLevel", AccessLevel)
    
    schema = make_executable_schema(
        load_schema_from_path("src/breedgraph/entrypoints/fastapi/graphql"),
        graphql_query,
        graphql_mutation,
        team,
        affiliations,
        affiliation,
        user,
        account,
        ontology_entry,
        location,
        layout,
        unit,
        dataset,
        record,
        datetime_scalar,
        snake_case_fallback_resolvers
        # access_level
    )
    
    logger.debug("GraphQL schema created successfully")
    return schema
