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
            " mutation ( $term: TermInput! ) { "
            "  ontologyCreateTerm( "
            "   term: $term  "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "term" : term_input
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
            " mutation ( $subject: SubjectInput! ) { "
            "  ontologyCreateSubject( "
            "   subject: $subject  "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "subject" : subject_input
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
            " mutation ( $trait: TraitInput! ) { "
            "  ontologyCreateTrait( "
            "   trait: $trait  "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "trait" : trait_input
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
            " mutation ( $observationMethod: ObservationMethodInput! ) { "
            "  ontologyCreateObservationMethod( "
            "   observationMethod: $observationMethod  "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "observationMethod" : observation_method_input
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
            " mutation ( $scale: ScaleInput! ) { "
            "  ontologyCreateScale( "
            "   scale: $scale  "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "scale" : scale_input
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
            " mutation ( $variable: VariableInput! ) { "
            "  ontologyCreateVariable( "
            "   variable: $variable  "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "variable" : variable_input
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
            " mutation ( $layoutType: LayoutTypeInput! ) { "
            "  ontologyCreateLayoutType( "
            "   layoutType: $layoutType  "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "layoutType" : layout_type_input
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
        entry_ids: List[int] | None = None,
):
    json={
        "query": (
            " query ( "
            "  $names: [String]"
            "  $labels: [OntologyEntryLabel]"
            "  $entryIds: [Int]"
            " ) { "
            "  ontologyEntries( "
            "    names: $names "
            "    labels: $labels "
            "    entryIds: $entryIds "
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
            "labels": [label.name for label in labels],
            "entryIds": entry_ids
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response


async def post_to_get_relationships(
        client,
        token: str,
        labels: List[OntologyRelationshipLabel] |None = None,
):
    json={
        "query": (
            " query ( "
            "  $labels: [OntologyRelationshipLabel]"
            " ) { "
            "  ontologyRelationships( "
            "    labels: $labels "
            "  ) { "
            "    status, "
            "    result { "
            "       id, "
            "       source_id,"
            "       target_id, "
            "       label "
            "   }, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "labels": [label.name for label in labels] if labels else None
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response

async def post_to_commit_version(
        client,
        token: str,
        version_change: VersionChange,
        comment: str | None = None
):
    json={
        "query": (
            " mutation ( "
            "   $versionChange: VersionChange! "
            "   $comment: String "
            " ) { "
            "  ontologyCommitVersion( "
            "   versionChange: $versionChange  "
            "   comment: $comment "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "versionChange" : version_change,
            "comment": comment
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response

async def post_to_commit_history(
        client,
        token: str,
        limit: int
):
    json={
        "query": (
            " query ( "
            "   $limit: Int "
            " ) { "
            "  ontologyCommitHistory( "
            "   limit: $limit "
            "  ) { "
            "    status, "
            "    result { version {major, minor, patch} , comment, time, user {id, name } }, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "limit" : limit
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response

async def post_to_update_term(
        client,
        token: str,
        term_update: dict
):
    json={
        "query": (
            " mutation ( $term: TermUpdate! ) { "
            "  ontologyUpdateTerm( "
            "   term: $term  "
            "  ) { "
            "    status, "
            "    result, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "term" : term_update
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response