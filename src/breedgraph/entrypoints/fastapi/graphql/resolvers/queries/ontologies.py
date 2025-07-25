from ariadne import ObjectType

from src.breedgraph.domain.model.ontology import OntologyOutput
from src.breedgraph.entrypoints.fastapi.graphql.decorators import graphql_payload, require_authentication
from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries import graphql_query

from src.breedgraph.entrypoints.fastapi.graphql.resolvers.queries.context_loaders import (
    inject_ontology
)

import logging
logger = logging.getLogger(__name__)

ontology_entry = ObjectType("OntologyEntry")

@graphql_query.field("ontology_entries")
@graphql_payload
@require_authentication
async def get_ontology_entries(_, info, name: str = None, label: str = None, version_id: int = None) -> [OntologyOutput]:
    await inject_ontology(info.context, version_id)
    ontology = info.context.get('ontology')
    entry_ids = [e[0] for e in ontology.get_entries(name, label)]
    return [ontology.to_output(e) for e in entry_ids]

#@ontology_entry.field("authors")
#def resolve_authors(obj, info):
#    raise NotImplementedError
#
#@ontology_entry.field("references")
#def resolve_references(obj, info):
#    raise NotImplementedError

# todo handle parent/children of Germplasm entries.
    #  Need to implement GQL for Germplasm first.

@ontology_entry.field("parents")
def resolve_parents(obj, info):
    ontology = info.context.get('ontology')
    return [ontology.to_output(parent) for parent in obj.parents]

@ontology_entry.field("children")
def resolve_children(obj, info):
    ontology = info.context.get('ontology')
    return [ontology.to_output(parent) for parent in obj.parents]

@ontology_entry.field("subjects")
def resolve_subjects(obj, info):
    ontology = info.context.get('ontology')
    return [ontology.to_output(subject) for subject in obj.subjects]

@ontology_entry.field("categories")
def resolve_categories(obj, info):
    ontology = info.context.get('ontology')
    return [ontology.to_output(category) for category in obj.categories]

@ontology_entry.field("trait")
def resolve_trait(obj, info):
    if obj.trait:
        ontology = info.context.get('ontology')
        return ontology.to_output(obj.trait)

@ontology_entry.field("condition")
def resolve_condition(obj, info):
    if obj.condition:
        ontology = info.context.get('ontology')
        return ontology.to_output(obj.condition)

@ontology_entry.field("exposure")
def resolve_exposure(obj, info):
    if obj.exposure:
        ontology = info.context.get('ontology')
        return ontology.to_output(obj.exposure)

@ontology_entry.field("method")
def resolve_method(obj, info):
    if obj.method:
        ontology = info.context.get('ontology')
        return ontology.to_output(obj.method)

@ontology_entry.field("scale")
def resolve_scale(obj, info):
    if obj.scale:
        ontology = info.context.get('ontology')
        return ontology.to_output(obj.scale)
