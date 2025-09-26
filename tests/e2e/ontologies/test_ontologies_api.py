import pytest

from src.breedgraph.domain.model.ontology import *
from src.breedgraph.service_layer.handlers.commands.setup import load_read_model
from tests.e2e.utils import get_verified_payload, assert_payload_success
from tests.e2e.ontologies.post_methods import (
    post_to_create_term,
    post_to_create_subject,
    post_to_create_trait,
    post_to_create_observation_method,
    post_to_create_scale,
    post_to_create_variable,
    post_to_create_layout_type,
    post_to_get_entries
)


@pytest.mark.usefixtures("session_database")
@pytest.mark.asyncio(scope="session")
async def test_create_term(client, first_user_login_token, lorem_text_generator):
    term_input = {
        'name': lorem_text_generator.new_text(10),
        'description': lorem_text_generator.new_text(20),
        'abbreviation': lorem_text_generator.new_text(5),
        'synonyms': [lorem_text_generator.new_text(5), lorem_text_generator.new_text(5)],
    }
    response = await post_to_create_term(
        client,
        token=first_user_login_token,
        term_input = term_input
    )
    assert_payload_success(get_verified_payload(response, "ontologyCreateTerm"))

@pytest.mark.asyncio(scope="session")
async def test_create_subject_relates_to_term(client, first_user_login_token, lorem_text_generator):
    response = await post_to_get_entries(client, token=first_user_login_token, labels=[OntologyEntryLabel.TERM])
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
        token=first_user_login_token,
        subject_input = subject_input
    )
    assert_payload_success(get_verified_payload(response, "ontologyCreateSubject"))
    response = await post_to_get_entries(client, token=first_user_login_token, labels=[OntologyEntryLabel.SUBJECT], names=[subject_input['name']])
    subject_payload = get_verified_payload(response, "ontologyEntries")
    assert subject_payload.get('result')[0].get('id')
    assert term_id in [i.get('id') for i in subject_payload.get('result')[0].get('terms')]

@pytest.mark.asyncio(scope="session")
async def test_create_trait_relates_to_subject(client, first_user_login_token, lorem_text_generator):
    response = await post_to_get_entries(
        client,
        token=first_user_login_token,
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
        token=first_user_login_token,
        trait_input= trait_input
    )
    assert_payload_success(get_verified_payload(response, "ontologyCreateTrait"))
    response = await post_to_get_entries(
        client,
        token=first_user_login_token,
        labels=[OntologyEntryLabel.TRAIT],
        names=[trait_input['name']],
    )
    trait_payload = get_verified_payload(response, "ontologyEntries")
    assert trait_payload.get('result')[0].get('id')
    assert subject_id in [i.get('id') for i in trait_payload.get('result')[0].get('subjects')]

@pytest.mark.asyncio(scope="session")
async def test_create_observation_method(client, first_user_login_token, lorem_text_generator):
    observation_method_input = {
        'name': lorem_text_generator.new_text(10),
        'description': lorem_text_generator.new_text(20),
        'abbreviation': lorem_text_generator.new_text(5),
        'synonyms': [lorem_text_generator.new_text(10), lorem_text_generator.new_text(5)],
        'observationType': ObservationMethodType.MEASUREMENT
    }
    response = await post_to_create_observation_method(
        client,
        token=first_user_login_token,
        observation_method_input=observation_method_input
    )
    assert_payload_success(get_verified_payload(response, "ontologyCreateObservationMethod"))
    response = await post_to_get_entries(
        client,
        token=first_user_login_token,
        labels=[OntologyEntryLabel.OBSERVATION_METHOD],
        names=[observation_method_input['name']]
    )
    method_payload = get_verified_payload(response, "ontologyEntries")
    assert method_payload.get('result')[0].get('id')

@pytest.mark.asyncio(scope="session")
async def test_create_scale(client, first_user_login_token, lorem_text_generator):
    scale_input = {
        'name': lorem_text_generator.new_text(10),
        'scaleType': ScaleType.NUMERICAL
    }
    response = await post_to_create_scale(
        client,
        token=first_user_login_token,
        scale_input = scale_input
    )
    assert_payload_success(get_verified_payload(response, "ontologyCreateScale"))
    response = await post_to_get_entries(
        client,
        token=first_user_login_token,
        labels=[OntologyEntryLabel.SCALE],
        names=[scale_input['name']]
    )
    method_payload = get_verified_payload(response, "ontologyEntries")
    assert method_payload.get('result')[0].get('id')

@pytest.mark.asyncio(scope="session")
async def test_create_variable(client, first_user_login_token, lorem_text_generator):
    trait_response = await post_to_get_entries(client, token=first_user_login_token, labels=[OntologyEntryLabel.TRAIT])
    trait_payload = get_verified_payload(trait_response, "ontologyEntries")
    trait_id = trait_payload.get('result')[0].get('id')

    method_response = await post_to_get_entries(client, token=first_user_login_token, labels=[OntologyEntryLabel.OBSERVATION_METHOD])
    method_payload = get_verified_payload(method_response, "ontologyEntries")
    method_id = method_payload.get('result')[0].get('id')

    scale_response = await post_to_get_entries(client, token=first_user_login_token, labels=[OntologyEntryLabel.SCALE])
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
        token=first_user_login_token,
        variable_input = variable_input
    )
    assert_payload_success(get_verified_payload(add_response, "ontologyCreateVariable"))

    variable_response = await post_to_get_entries(
        client,
        token=first_user_login_token,
        labels=[OntologyEntryLabel.VARIABLE],
        names=[variable_input['name']]
    )
    variable_payload = get_verified_payload(variable_response, "ontologyEntries")
    assert variable_payload.get('result')[0].get('id')
    assert variable_payload.get('result')[0].get('trait').get('id') == trait_id
    assert variable_payload.get('result')[0].get('observationMethod').get('id') == method_id
    assert variable_payload.get('result')[0].get('scale').get('id') == scale_id

@pytest.mark.asyncio(scope="session")
async def test_create_layout_type(client, first_user_login_token, lorem_text_generator):
    layout_type_input = {
        'name': lorem_text_generator.new_text(),
        'axes': [AxisType.CARTESIAN, AxisType.CARTESIAN]

    }
    response = await post_to_create_layout_type(
        client,
        token=first_user_login_token,
        layout_type_input=layout_type_input
    )
    assert_payload_success(get_verified_payload(response, "ontologyCreateLayoutType"))
    response = await post_to_get_entries(client, token=first_user_login_token, labels=[OntologyEntryLabel.LAYOUT_TYPE], names=layout_type_input['name'])
    layout_payload = get_verified_payload(response, "ontologyEntries")
    assert layout_payload.get('result')[0].get('id')
    assert layout_payload.get('result')[0].get('axes') == layout_type_input['axes']
