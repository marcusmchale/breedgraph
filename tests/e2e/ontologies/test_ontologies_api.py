import pytest

from src.breedgraph.custom_exceptions import NoResultFoundError, UnauthorisedOperationError
from src.breedgraph.domain.model.ontology import *

from tests.e2e.utils import get_verified_payload, assert_payload_success
from tests.e2e.ontologies.post_methods import (
    post_to_create_term,
    post_to_create_subject,
    post_to_create_trait,
    post_to_create_observation_method,
    post_to_create_scale,
    post_to_create_variable,
    post_to_create_layout_type,
    post_to_get_entries,
    post_to_commit_version,
    post_to_commit_history,
    post_to_get_ontology,
    post_to_update_term
)


@pytest.mark.asyncio(loop_scope="session")
async def test_create_term(
        ontology_build_context,
        login_token_factory,
        client,
        lorem_text_generator
):
    user_id = ontology_build_context['user_id']
    login_token = login_token_factory(user_id)
    term_input = {
        'name': lorem_text_generator.new_text(10),
        'description': lorem_text_generator.new_text(20),
        'abbreviation': lorem_text_generator.new_text(5),
        'synonyms': [lorem_text_generator.new_text(5), lorem_text_generator.new_text(5)],
    }
    response = await post_to_create_term(
        client,
        token=login_token,
        term_input = term_input
    )
    assert_payload_success(get_verified_payload(response, "ontologyCreateTerm"))

@pytest.mark.asyncio(loop_scope="session")
async def test_create_subject_relates_to_term(
        ontology_build_context,
        login_token_factory,
        client,
        lorem_text_generator
):
    user_id = ontology_build_context['user_id']
    login_token = login_token_factory(user_id)
    response = await post_to_get_entries(client, token=login_token, labels=[OntologyEntryLabel.TERM])

    term_payload = get_verified_payload(response, "ontologyEntries")
    term_id = term_payload.get('result')[0].get('id')
    subject_input = {
        'name': lorem_text_generator.new_text(10),
        'description':lorem_text_generator.new_text(20),
        'synonyms':[lorem_text_generator.new_text(5)],
        'termIds': [term_id]
    }
    response = await post_to_create_subject(
        client,
        token=login_token,
        subject_input = subject_input
    )
    assert_payload_success(get_verified_payload(response, "ontologyCreateSubject"))

    # Verify the linked term is in the draft
    response = await post_to_get_entries(client, token=login_token, labels=[OntologyEntryLabel.SUBJECT], draft=True)
    subject_payload = get_verified_payload(response, "ontologyEntries")
    if not any(
            term.get("id") == term_id
            for subject in subject_payload.get("result", [])
            for term in subject.get("terms", [])
    ):
        raise NoResultFoundError("Term not found for the created subject")

@pytest.mark.asyncio(loop_scope="session")
async def test_create_trait_relates_to_subject(
        ontology_build_context,
        login_token_factory,
        client,
        lorem_text_generator
):
    user_id = ontology_build_context['user_id']
    login_token = login_token_factory(user_id)
    response = await post_to_get_entries(
        client,
        token=login_token,
        labels=[OntologyEntryLabel.SUBJECT]
    )

    subject_payload = get_verified_payload(response, "ontologyEntries")
    subject_id = subject_payload.get('result')[0].get('id')
    trait_input = {
        'name': lorem_text_generator.new_text(10),
        'description': lorem_text_generator.new_text(20),
        'abbreviation': lorem_text_generator.new_text(5),
        'synonyms': [lorem_text_generator.new_text(10), lorem_text_generator.new_text(5)],
        'subjectIds': [subject_id]
    }
    response = await post_to_create_trait(
        client,
        token=login_token,
        trait_input= trait_input
    )
    assert_payload_success(get_verified_payload(response, "ontologyCreateTrait"))
    response = await post_to_get_entries(
        client,
        token=login_token,
        labels=[OntologyEntryLabel.TRAIT],
        draft=True
    )
    trait_payload = get_verified_payload(response, "ontologyEntries")
    if not any(
            subject.get("id") == subject_id
            for trait in trait_payload.get("result", [])
            for subject in trait.get("subjects", [])
    ):
        raise NoResultFoundError("Subject not found for the created trait")


@pytest.mark.asyncio(loop_scope="session")
async def test_create_observation_method(
        ontology_build_context,
        login_token_factory,
        client,
        lorem_text_generator
):
    user_id = ontology_build_context['user_id']
    login_token = login_token_factory(user_id)
    observation_method_input = {
        'name': lorem_text_generator.new_text(10),
        'description': lorem_text_generator.new_text(20),
        'abbreviation': lorem_text_generator.new_text(5),
        'synonyms': [lorem_text_generator.new_text(10), lorem_text_generator.new_text(5)],
        'observationType': ObservationMethodType.MEASUREMENT
    }
    response = await post_to_create_observation_method(
        client,
        token=login_token,
        observation_method_input=observation_method_input
    )
    assert_payload_success(get_verified_payload(response, "ontologyCreateObservationMethod"))
    response = await post_to_get_entries(
        client,
        token=login_token,
        labels=[OntologyEntryLabel.OBSERVATION_METHOD]
    )
    method_payload = get_verified_payload(response, "ontologyEntries")
    assert method_payload.get('result')[0].get('id')

@pytest.mark.asyncio(loop_scope="session")
async def test_create_scale(
        ontology_build_context,
        login_token_factory,
        client,
        lorem_text_generator
):
    user_id = ontology_build_context['user_id']
    login_token = login_token_factory(user_id)
    scale_input = {
        'name': lorem_text_generator.new_text(10),
        'scaleType': ScaleType.NUMERICAL
    }
    response = await post_to_create_scale(
        client,
        token=login_token,
        scale_input = scale_input
    )
    assert_payload_success(get_verified_payload(response, "ontologyCreateScale"))
    response = await post_to_get_entries(
        client,
        token=login_token,
        labels=[OntologyEntryLabel.SCALE]
    )
    method_payload = get_verified_payload(response, "ontologyEntries")
    assert method_payload.get('result')[0].get('id')

@pytest.mark.asyncio(loop_scope="session")
async def test_create_variable(
        ontology_build_context,
        login_token_factory,
        client,
        lorem_text_generator
):
    user_id = ontology_build_context['user_id']
    login_token = login_token_factory(user_id)
    trait_response = await post_to_get_entries(client, token=login_token, labels=[OntologyEntryLabel.TRAIT])
    trait_payload = get_verified_payload(trait_response, "ontologyEntries")
    trait_id = trait_payload.get('result')[0].get('id')

    method_response = await post_to_get_entries(client, token=login_token, labels=[OntologyEntryLabel.OBSERVATION_METHOD])
    method_payload = get_verified_payload(method_response, "ontologyEntries")
    method_id = method_payload.get('result')[0].get('id')

    scale_response = await post_to_get_entries(client, token=login_token, labels=[OntologyEntryLabel.SCALE])
    scale_payload = get_verified_payload(scale_response, "ontologyEntries")
    scale_id = scale_payload.get('result')[0].get('id')

    variable_input = {
        'name': lorem_text_generator.new_text(10),
        'traitId': trait_id,
        'observationMethodId': method_id,
        'scaleId': scale_id
    }
    add_response = await post_to_create_variable(
        client,
        token=login_token,
        variable_input = variable_input
    )
    assert_payload_success(get_verified_payload(add_response, "ontologyCreateVariable"))

    variable_response = await post_to_get_entries(
        client,
        token=login_token,
        labels=[OntologyEntryLabel.VARIABLE],
        draft=True
    )
    variable_payload = get_verified_payload(variable_response, "ontologyEntries")
    assert variable_payload.get('result')[0].get('id')
    assert variable_payload.get('result')[0].get('trait').get('id') == trait_id
    assert variable_payload.get('result')[0].get('observationMethod').get('id') == method_id
    assert variable_payload.get('result')[0].get('scale').get('id') == scale_id

@pytest.mark.asyncio(loop_scope="session")
async def test_create_layout_type(
        ontology_build_context,
        login_token_factory,
        client,
        lorem_text_generator
):
    user_id = ontology_build_context['user_id']
    login_token = login_token_factory(user_id)
    layout_type_input = {
        'name': lorem_text_generator.new_text(),
        'axes': [AxisType.CARTESIAN, AxisType.CARTESIAN]

    }
    response = await post_to_create_layout_type(
        client,
        token=login_token,
        layout_type_input=layout_type_input
    )
    assert_payload_success(get_verified_payload(response, "ontologyCreateLayoutType"))
    response = await post_to_get_entries(client, token=login_token, labels=[OntologyEntryLabel.LAYOUT_TYPE])
    layout_payload = get_verified_payload(response, "ontologyEntries")
    assert layout_payload.get('result')[0].get('id')
    assert layout_payload.get('result')[0].get('axes') == layout_type_input['axes']

@pytest.mark.asyncio(loop_scope="session")
async def test_commit_version(
        ontology_build_context,
        login_token_factory,
        client
):
    # commits not available to contributor role users
    with pytest.raises(AssertionError):
        user_id = ontology_build_context['user_id_2']
        login_token = login_token_factory(user_id)
        response = await post_to_commit_version(
            client,
            token=login_token,
            version_change=VersionChange.MAJOR,
            comment="Test major change"
        )
        payload = get_verified_payload(response, "ontologyCommitVersion")
        assert_payload_success(payload)

    user_id = ontology_build_context['user_id']
    login_token = login_token_factory(user_id)
    response = await post_to_commit_version(
        client,
        token=login_token,
        version_change=VersionChange.MAJOR,
        comment="Test major change"
    )
    assert_payload_success(get_verified_payload(response, "ontologyCommitVersion"))
    response = await post_to_commit_history(client, token=login_token, limit=3)
    payload = get_verified_payload(response, "ontologyCommitHistory")
    assert_payload_success(payload)

    assert payload.get('result')[0].get('user').get('id') == user_id
    assert payload.get('result')[0].get('version').get('major') > 0
    assert payload.get('result')[0].get('comment') == 'Test major change'

@pytest.mark.asyncio(loop_scope="session")
async def test_get_ontology(
        ontology_build_context,
        login_token_factory,
        client):
    user_id = ontology_build_context['user_id']
    login_token = login_token_factory(user_id)
    response = await post_to_get_ontology(
        client,
        token=login_token
    )
    payload = get_verified_payload(response, "ontology")
    assert_payload_success(payload)
    assert payload.get('result').get('entries')
    assert payload.get('result').get('relationships')
    assert payload.get('result').get('versionId')

@pytest.mark.asyncio(loop_scope="session")
async def test_update_create_relationships(
        ontology_build_context,
        login_token_factory,
        client,
        lorem_text_generator
):
    user_id = ontology_build_context['user_id']
    login_token = login_token_factory(user_id)
    term_response = await post_to_get_entries(client, token=login_token, labels=[OntologyEntryLabel.TERM])
    term_payload = get_verified_payload(term_response, "ontologyEntries")
    parent_term_id = term_payload.get('result')[0].get('id')

    subject_response = await post_to_get_entries(client, token=login_token, labels=[OntologyEntryLabel.SUBJECT])
    subject_payload = get_verified_payload(subject_response, "ontologyEntries")
    subject_id = subject_payload.get('result')[0].get('id')

    child_term_input = {
        'name': lorem_text_generator.new_text(10)
    }
    response = await post_to_create_term(
        client,
        token=login_token,
        term_input = child_term_input
    )
    assert_payload_success(get_verified_payload(response, "ontologyCreateTerm"))

    child_term_response = await post_to_get_entries(client, token=login_token, labels=[OntologyEntryLabel.TERM])
    child_term_payload = get_verified_payload(child_term_response, "ontologyEntries")
    child_term_id = child_term_payload.get('result')[0].get('id')
    child_term_update = {
        'id': child_term_id,
        'parentIds': [parent_term_id],
        'subjectIds': [subject_id]
    }
    update_response = await post_to_update_term(
        client,
        token=login_token,
        term_update=child_term_update
    )
    assert_payload_success(get_verified_payload(update_response, "ontologyUpdateTerm"))

