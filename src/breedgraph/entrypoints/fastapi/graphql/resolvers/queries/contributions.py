from ariadne import ObjectType

from breedgraph.domain.model.contributions import Contribution
from breedgraph.service_layer.queries.read_models import OntologyViewMode
from breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import resolve_people, update_ontology_map

from ..registry import graphql_resolvers

contribution = ObjectType("Contribution")
graphql_resolvers.register_type_resolvers(contribution)


@contribution.field("person")
async def resolve_contribution_person(obj: Contribution, info):
    people = await resolve_people(info.context, [obj.person])
    return people[0] if people else None


@contribution.field("roles")
async def resolve_contribution_roles(obj: Contribution, info):
    # as entries referred to from outside the ontology, like a study's design
    await update_ontology_map(context=info.context, entry_ids=obj.roles, view=OntologyViewMode.REFERENTIAL)
    ontology_map = info.context.get('ontology_map')
    return [ontology_map[role_id] for role_id in obj.roles if role_id in ontology_map]
