from ariadne import ObjectType

from breedgraph.domain.model.contributions import Contribution
from breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import resolve_people
from breedgraph.entrypoints.fastapi.graphql.resolvers.queries.ontology import resolve_ontology_entries

from ..registry import graphql_resolvers

contribution = ObjectType("Contribution")
graphql_resolvers.register_type_resolvers(contribution)


@contribution.field("person")
async def resolve_contribution_person(obj: Contribution, info):
    people = await resolve_people(info.context, [obj.person])
    return people[0] if people else None


@contribution.field("roles")
async def resolve_contribution_roles(obj: Contribution, info):
    return await resolve_ontology_entries(info.context, entry_ids=obj.roles)
