from ariadne import (
    make_executable_schema,
    load_schema_from_path,
    snake_case_fallback_resolvers
)

from src.breedgraph.entrypoints.fastapi.graphql.resolvers import graphql_resolvers

import logging

logger = logging.getLogger(__name__)


def create_graphql_schema():
    """Create and return the GraphQL schema with all resolvers bound"""
    logger.debug("Building GraphQL schema")

    # Get all registered resolvers from the registry
    all_resolvers = graphql_resolvers.get_all()

    # Add fallback resolvers
    all_resolvers.append(snake_case_fallback_resolvers)

    schema = make_executable_schema(
        load_schema_from_path("src/breedgraph/entrypoints/fastapi/graphql"),
        *all_resolvers
    )

    logger.debug(f"GraphQL schema created with {len(all_resolvers)} resolvers:")
    logger.debug(f"  - {len(graphql_resolvers.get_queries())} query resolvers")
    logger.debug(f"  - {len(graphql_resolvers.get_mutations())} mutation resolvers")
    logger.debug(f"  - {len(graphql_resolvers.get_types())} type resolvers")
    logger.debug(f"  - {len(graphql_resolvers.scalars)} scalars")
    logger.debug(f"  - {len(graphql_resolvers.enums)} enums")

    return schema