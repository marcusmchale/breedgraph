"""
A deprecated entry is read whole until the commit removes it, and after, in the versions that had it: a variable keeps
its trait, method and scale, which GraphQL requires, in the editorial view (deprecated with it, and removed with it in
the version that removed them), the published view (the published version still has them) and the view of a version
before the commit that removed them.
"""
import pytest

from breedgraph.domain.model.ontology import VersionChange
from breedgraph.service_layer.queries.read_models import OntologyViewMode

from tests.breedgraph.e2e.ontologies.post_methods import post_to_create_variable, post_to_commit_version
from tests.breedgraph.e2e.utils import get_verified_payload, assert_payload_success, with_auth
from breedgraph.config import GQL_API_PATH

VARIABLE_FIELDS = "... on Variable { id name phase versionId trait { id } observationMethod { id } scale { id } }"


async def _post(client, token: str, query: str, variables: dict | None = None):
    headers = with_auth(csrf_token=client.headers["X-CSRF-Token"], auth_token=token)
    return await client.post(GQL_API_PATH, json={"query": query, "variables": variables or {}}, headers=headers)


async def ontology_variable(client, token, variable_id: str, view: OntologyViewMode, version_id: str | None = None):
    """The variable as the whole ontology gives it in a view, or None; the query must succeed"""
    response = await _post(
        client, token,
        " query ( $view: OntologyView, $versionId: ID ) { ontology( view: $view, versionId: $versionId ) { "
        f"  status, result {{ entries {{ {VARIABLE_FIELDS} }} }}, errors {{ message }} }} }} ",
        {"view": view.value, "versionId": version_id}
    )
    payload = get_verified_payload(response, "ontology")
    assert_payload_success(payload)
    return next((entry for entry in payload['result']['entries'] if entry.get('id') == variable_id), None)


async def relationships(client, token, variable_id: str, version_id: str) -> set[str]:
    response = await _post(
        client, token,
        " query ( $versionId: ID, $ids: [ID!]! ) { ontologyRelationships( versionId: $versionId, entryIds: $ids ) { "
        "  status, result { label }, errors { message } } } ",
        {"versionId": version_id, "ids": [variable_id]}
    )
    payload = get_verified_payload(response, "ontologyRelationships")
    assert_payload_success(payload)
    return {relationship['label'] for relationship in payload['result']}


async def commit(client, token, comment: str):
    assert_payload_success(get_verified_payload(
        await post_to_commit_version(client, token=token, version_change=VersionChange.MINOR, comment=comment),
        "ontologyCommitVersion"
    ))


@pytest.mark.asyncio(loop_scope="session")
async def test_a_deprecated_variable_is_read_whole(ontology_build_context, login_token_factory, client, lorem_text_generator):
    context = ontology_build_context
    token = login_token_factory(context['user_id'])
    defined_by = {
        'trait': str(context['ontology_trait']),
        'observationMethod': str(context['ontology_observation_method']),
        'scale': str(context['ontology_scale'])
    }
    assert_payload_success(get_verified_payload(await post_to_create_variable(client, token=token, variable_input={
        'name': lorem_text_generator.new_text(10),
        'traitId': defined_by['trait'],
        'observationMethodId': defined_by['observationMethod'],
        'scaleId': defined_by['scale']
    }), "ontologyCreateVariable"))
    await commit(client, token, "A variable to deprecate")
    variable = next(
        entry for entry in (await _post(
            client, token,
            f" query {{ ontologyEntries( view: PUBLISHED, labels: [VARIABLE] ) {{ result {{ {VARIABLE_FIELDS} }} }} }} "
        )).json()['data']['ontologyEntries']['result']
        if entry['trait']['id'] == defined_by['trait'] and entry['scale']['id'] == defined_by['scale']
    )
    variable_id, version_with = variable['id'], variable['versionId']
    whole = lambda entry: {field: entry[field]['id'] for field in defined_by}

    response = await _post(client, token, " mutation ( $ids: [ID!]! ) { ontologyDeprecateEntries( ids: $ids ) { status, result, errors { message } } } ",
                           {"ids": [variable_id]})
    assert_payload_success(get_verified_payload(response, "ontologyDeprecateEntries"))

    # until the commit: deprecated in the editorial view, as published in the published one, whole in both
    editorial = await ontology_variable(client, token, variable_id, OntologyViewMode.EDITORIAL)
    assert editorial['phase'] == 'DEPRECATED'
    assert whole(editorial) == defined_by
    assert whole(await ontology_variable(client, token, variable_id, OntologyViewMode.PUBLISHED)) == defined_by
    assert await relationships(client, token, variable_id, version_with) >= {'DESCRIBES_TRAIT', 'USES_OBSERVATION_METHOD', 'USES_SCALE'}

    # removed by the commit: whole in the editorial view of the version that removed it, gone from the published one,
    # and whole still in the version before
    await commit(client, token, "The variable removed")
    removed = await ontology_variable(client, token, variable_id, OntologyViewMode.EDITORIAL)
    assert removed is None or (removed['phase'] == 'REMOVED' and whole(removed) == defined_by)
    assert await ontology_variable(client, token, variable_id, OntologyViewMode.PUBLISHED) is None
    assert whole(await ontology_variable(client, token, variable_id, OntologyViewMode.PUBLISHED, version_with)) == defined_by
    assert await relationships(client, token, variable_id, version_with) >= {'DESCRIBES_TRAIT', 'USES_OBSERVATION_METHOD', 'USES_SCALE'}
