from src.breedgraph.config import GQL_API_PATH
from src.breedgraph.domain.model.ontology import *

from typing import List
from tests.e2e.utils import with_auth

async def post_to_create_term(
        client,
        token: str,
        term_input: dict
):
    json={
        "query": (
            " mutation ( $termInput: TermInput! ) { "
            "  ontologyCreateTerm( "
            "   termInput: $termInput  "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "termInput" : term_input
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response

async def post_to_create_subject(
        client,
        token: str,
        subject_input: dict
):
    json={
        "query": (
            " mutation ( $subjectInput: SubjectInput! ) { "
            "  ontologyCreateSubject( "
            "   subjectInput: $subjectInput  "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "subjectInput" : subject_input
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response

async def post_to_create_trait(
        client,
        token: str,
        trait_input: dict
):
    json={
        "query": (
            " mutation ( $traitInput: TraitInput! ) { "
            "  ontologyCreateTrait( "
            "   traitInput: $traitInput  "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "traitInput" : trait_input
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response

async def post_to_create_observation_method(
        client,
        token: str,
        observation_method_input: dict
):
    json={
        "query": (
            " mutation ( $observationMethodInput: ObservationMethodInput! ) { "
            "  ontologyCreateObservationMethod( "
            "   observationMethodInput: $observationMethodInput  "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "observationMethodInput" : observation_method_input
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response

async def post_to_create_scale(
        client,
        token: str,
        scale_input: dict
):
    json={
        "query": (
            " mutation ( $scaleInput: ScaleInput! ) { "
            "  ontologyCreateScale( "
            "   scaleInput: $scaleInput  "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "scaleInput" : scale_input
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response

async def post_to_create_variable(
        client,
        token: str,
        variable_input: dict
):
    json={
        "query": (
            " mutation ( $variableInput: VariableInput! ) { "
            "  ontologyCreateVariable( "
            "   variableInput: $variableInput  "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "variableInput" : variable_input
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response

async def post_to_create_layout_type(
        client,
        token: str,
        layout_type_input: dict
):
    json={
        "query": (
            " mutation ( $layoutTypeInput: LayoutTypeInput! ) { "
            "  ontologyCreateLayoutType( "
            "   layoutTypeInput: $layoutTypeInput  "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "layoutTypeInput" : layout_type_input
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response


async def post_to_get_entries(
        client,
        token: str,
        names: List[str] | None = None,
        labels: List[OntologyEntryLabel] |None = None,
):
    json={
        "query": (
            " query ( "
            "  $names: [String]"
            "  $labels: [OntologyEntryLabel]"
            " ) { "
            "  ontologyEntries( "
            "    names: $names "
            "    labels: $labels "
            "  ) { "
            "    status, "
            "    result { "
            "       id, "
            "       name,"
            "       parents { id, name }, "
            "       children { id, name } "
            "       ... on RelatedToTerms { terms { id, name } }"
            "       ... on Subject { traits { id, name } , conditions { id, name } } "
            "       ... on Trait { subjects { id, name }, variables { id, name } } "
            "       ... on Condition { subjects { id, name } , factors { id, name } } "
            "       ... on Scale { scaleType, categories  { id, name } , variables { id, name } , factors { id, name } }"
            "       ... on Category { scales  { id, name } }"
            "       ... on ObservationMethod { observationType, variables  { id, name } } " 
            "       ... on Variable { trait { id, name } , observationMethod { id, name }, scale  { id, name } } "
            "       ... on ControlMethod { controlType, factors { id, name } } "
            "       ... on Factor { condition { id, name }, controlMethod { id, name }, scale { id, name } } "
            "       ... on Event { variables { id, name }, factors { id, name } } "
            "       ... on LayoutType { axes } "
            "   }, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "names": names,
            "labels": [label.name for label in labels]
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response