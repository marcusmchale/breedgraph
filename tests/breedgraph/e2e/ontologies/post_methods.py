from breedgraph.config import GQL_API_PATH
from breedgraph.domain.model.ontology import *

from typing import List

from breedgraph.service_layer.queries.read_models import OntologyViewMode
from tests.breedgraph.e2e.utils import with_auth

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
            "    status "
            "    result "
            "    errors { name message } "
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
            "    status "
            "    result "
            "    errors { name message } "
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
            "    status "
            "    result "
            "    errors { name message } "
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
            "    status "
            "    result "
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
            "    status "
            "    result "
            "    errors { name message } "
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
            "    status "
            "    result "
            "    errors { name message } "
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


async def post_to_create_record_group_type(
        client,
        token: str,
        record_group_type_input: dict
):
    json={
        "query": (
            " mutation ( $recordGroupType: RecordGroupTypeInput! ) { "
            "  ontologyCreateRecordGroupType( "
            "   recordGroupType: $recordGroupType  "
            "  ) { "
            "    status "
            "    result "
            "    errors { name message } "
            "  } "
            " } "
        ),
        "variables": {
            "recordGroupType" : record_group_type_input
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response


async def post_to_update_record_group_type(
        client,
        token: str,
        record_group_type_update: dict
):
    json={
        "query": (
            " mutation ( $recordGroupType: RecordGroupTypeUpdate! ) { "
            "  ontologyUpdateRecordGroupType( "
            "   recordGroupType: $recordGroupType  "
            "  ) { "
            "    status "
            "    result "
            "    errors { name message } "
            "  } "
            " } "
        ),
        "variables": {
            "recordGroupType" : record_group_type_update
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response


async def post_to_create_role(client, token: str, role_input: dict):
    json={
        "query": (
            " mutation ( $role: RoleInput! ) { "
            "  ontologyCreateRole( role: $role ) { status result errors { name message } } "
            " } "
        ),
        "variables": {"role": role_input}
    }
    headers = with_auth(csrf_token=client.headers["X-CSRF-Token"], auth_token=token)
    return await client.post(GQL_API_PATH, json=json, headers=headers)


async def post_to_update_role(client, token: str, role_update: dict):
    json={
        "query": (
            " mutation ( $role: RoleUpdate! ) { "
            "  ontologyUpdateRole( role: $role ) { status result errors { name message } } "
            " } "
        ),
        "variables": {"role": role_update}
    }
    headers = with_auth(csrf_token=client.headers["X-CSRF-Token"], auth_token=token)
    return await client.post(GQL_API_PATH, json=json, headers=headers)


async def post_to_get_entries(
        client,
        token: str,
        labels: List[OntologyEntryLabel] |None = None,
        entry_ids: List[int] | None = None,
        view: OntologyViewMode = OntologyViewMode.PUBLISHED
):
    json={
        "query": (
            " query ( "
            "  $labels: [OntologyNodeLabel!]"
            "  $ids: [ID!]"
            "  $view: OntologyView "
            " ) { "
            "  ontologyEntries( "
            "    labels: $labels "
            "    ids: $ids "
            "    view: $view "
            "  ) { "
            "    status "
            "    result { "
            "       ... on OntologyNodeInterface { id name description } "
            "       ... on OntologyRelationships { parents { id name } } "
            "       ... on OntologyRelationships { children { id name } } "
            "       ... on RelatedToTerms { terms { id name } }"
            "       ... on Subject { traits { id name }  conditions { id name } } "
            "       ... on Trait { subjects { id name } variables { id name } } "
            "       ... on Condition { subjects { id name } factors { id name } } "
            "       ... on Scale { scaleType categories  { id name } variables { id name }  factors { id name } }"
            "       ... on Category { scales  { id name } }"
            "       ... on ObservationMethod { observationType variables  { id name } } " 
            "       ... on Variable { trait { id name }  observationMethod { id name } scale  { id name } } "
            "       ... on ControlMethod { controlType factors { id name } } "
            "       ... on Factor { condition { id name } controlMethod { id name } scale { id name } } "
            "       ... on Event { variables { id name } factors { id name } } "
            "       ... on LayoutType { axes } "
            "       ... on RecordGroupType { defaultExtent parents { id name defaultExtent } } "
            "       ... on Term { roles { id name } } "
            "   } "
            "    errors { name message } "
            "  } "
            " } "
        ),
        "variables": {
            "labels": [label.name for label in labels],
            "ids": entry_ids,
            "view": view.value
        }
    }
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=token
    )
    response = await client.post(GQL_API_PATH, json=json, headers=headers)
    return response


async def post_to_get_ontology(
        client,
        token: str,
        version_id: str|None = None,
        view: OntologyViewMode = OntologyViewMode.PUBLISHED
):
    json={
        "query": (
            " query ( "
            "  $versionId: ID"
            "  $view: OntologyView "
            " ) { "
            "  ontology( "
            "    versionId: $versionId "
            "    view: $view "
            "  ) { "
            "    status, "
            "    result { "
            "       version { major minor patch } , "
            "       entries { ... on OntologyNodeInterface { id name description } } "
            "       relationships { id label sourceId targetId } "
            "   }, "
            "    errors { name, message } "
            "  } "
            " } "
        ),
        "variables": {
            "versionId": version_id,
            "view": view.value
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
            "    status "
            "    result "
            "    errors { name message } "
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
            "    result { version {major minor patch} comment time user {id name } }, "
            "    errors { name message } "
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
            "    status "
            "    result "
            "    errors { name message } "
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