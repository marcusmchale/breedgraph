import pytest

from src.breedgraph.domain.model.ontology import ObservationMethodType, ScaleType
from tests.e2e.payload_helpers import get_verified_payload, assert_payload_success
from tests.e2e.ontologies.post_methods import post_to_add_entry, post_to_get_entries


@pytest.mark.usefixtures("session_database")
@pytest.mark.asyncio(scope="session")
async def test_add_term(client, first_user_login_token, lorem_text_generator):
    response = await post_to_add_entry(
        client,
        token=first_user_login_token,
        label="Term",
        name=lorem_text_generator.new_text(10),
        description=lorem_text_generator.new_text(20),
        abbreviation=lorem_text_generator.new_text(5),
        synonyms=[lorem_text_generator.new_text(10),lorem_text_generator.new_text(5)]
    )
    assert_payload_success(get_verified_payload(response, "ontology_add_entry"))

@pytest.mark.asyncio(scope="session")
async def test_add_subject(client, first_user_login_token, lorem_text_generator):
    response = await post_to_get_entries(client, token=first_user_login_token, label="Term")
    term_payload = get_verified_payload(response, "ontology_entries")
    term_id = term_payload.get('result')[0].get('id')
    subject_name = lorem_text_generator.new_text(10)
    response = await post_to_add_entry(
        client,
        token=first_user_login_token,
        label="Subject",
        name=subject_name,
        description=lorem_text_generator.new_text(20),
        abbreviation=lorem_text_generator.new_text(5),
        synonyms=[lorem_text_generator.new_text(10),lorem_text_generator.new_text(5)],
        parents=[term_id],
    )
    assert_payload_success(get_verified_payload(response, "ontology_add_entry"))
    response = await post_to_get_entries(client, token=first_user_login_token, label="Subject", name=subject_name)
    subject_payload = get_verified_payload(response, "ontology_entries")
    assert subject_payload.get('result')[0].get('id')
    assert term_id in [i.get('id') for i in subject_payload.get('result')[0].get('parents')]

@pytest.mark.asyncio(scope="session")
async def test_add_trait(client, first_user_login_token, lorem_text_generator):
    response = await post_to_get_entries(
        client,
        token=first_user_login_token,
        label="Subject"
    )

    subject_payload = get_verified_payload(response, "ontology_entries")
    subject_id = subject_payload.get('result')[0].get('id')
    trait_name = lorem_text_generator.new_text(10)
    response = await post_to_add_entry(
        client,
        token=first_user_login_token,
        label="Trait",
        name=trait_name,
        description=lorem_text_generator.new_text(20),
        abbreviation=lorem_text_generator.new_text(5),
        synonyms=[lorem_text_generator.new_text(10), lorem_text_generator.new_text(5)],
        subjects=[subject_id],
    )
    assert_payload_success(get_verified_payload(response, "ontology_add_entry"))
    response = await post_to_get_entries(
        client,
        token=first_user_login_token,
        label="Trait",
        name=trait_name
    )
    trait_payload = get_verified_payload(response, "ontology_entries")
    assert trait_payload.get('result')[0].get('id')
    assert subject_id in [i.get('id') for i in trait_payload.get('result')[0].get('subjects')]

@pytest.mark.asyncio(scope="session")
async def test_add_method(client, first_user_login_token, lorem_text_generator):
    method_name = lorem_text_generator.new_text(10)
    response = await post_to_add_entry(
        client,
        token=first_user_login_token,
        label="ObservationMethod",
        name=method_name,
        description=lorem_text_generator.new_text(20),
        abbreviation=lorem_text_generator.new_text(5),
        synonyms=[lorem_text_generator.new_text(10), lorem_text_generator.new_text(5)],
        observation_type=ObservationMethodType.MEASUREMENT
    )
    assert_payload_success(get_verified_payload(response, "ontology_add_entry"))
    response = await post_to_get_entries(
        client,
        token=first_user_login_token,
        label="ObservationMethod",
        name=method_name
    )
    method_payload = get_verified_payload(response, "ontology_entries")
    assert method_payload.get('result')[0].get('id')

@pytest.mark.asyncio(scope="session")
async def test_add_scale(client, first_user_login_token, lorem_text_generator):
    scale_name = lorem_text_generator.new_text(10)
    response = await post_to_add_entry(
        client,
        token=first_user_login_token,
        label="Scale",
        name=scale_name,
        description=lorem_text_generator.new_text(20),
        abbreviation=lorem_text_generator.new_text(5),
        synonyms=[lorem_text_generator.new_text(10), lorem_text_generator.new_text(5)],
        scale_type=ScaleType.NUMERICAL
    )
    assert_payload_success(get_verified_payload(response, "ontology_add_entry"))
    response = await post_to_get_entries(
        client,
        token=first_user_login_token,
        label="Scale",
        name=scale_name
    )
    method_payload = get_verified_payload(response, "ontology_entries")
    assert method_payload.get('result')[0].get('id')

@pytest.mark.asyncio(scope="session")
async def test_add_variable(client, first_user_login_token, lorem_text_generator):
    trait_response = await post_to_get_entries(client, token=first_user_login_token, label="Trait")
    trait_payload = get_verified_payload(trait_response, "ontology_entries")
    trait_id = trait_payload.get('result')[0].get('id')

    method_response = await post_to_get_entries(client, token=first_user_login_token, label="ObservationMethod")
    method_payload = get_verified_payload(method_response, "ontology_entries")
    method_id = method_payload.get('result')[0].get('id')

    scale_response = await post_to_get_entries(client, token=first_user_login_token, label="Scale")
    scale_payload = get_verified_payload(scale_response, "ontology_entries")
    scale_id = scale_payload.get('result')[0].get('id')

    variable_name = lorem_text_generator.new_text(10)
    add_response = await post_to_add_entry(
        client,
        token=first_user_login_token,
        label="Variable",
        name=variable_name,
        description=lorem_text_generator.new_text(20),
        abbreviation=lorem_text_generator.new_text(5),
        synonyms=[lorem_text_generator.new_text(10), lorem_text_generator.new_text(5)],
        trait=trait_id,
        method=method_id,
        scale=scale_id
    )
    assert_payload_success(get_verified_payload(add_response, "ontology_add_entry"))

    variable_response = await post_to_get_entries(
        client,
        token=first_user_login_token,
        label="Variable",
        name=variable_name
    )
    variable_payload = get_verified_payload(variable_response, "ontology_entries")
    assert variable_payload.get('result')[0].get('id')
    assert variable_payload.get('result')[0].get('trait').get('id') == trait_id
    assert variable_payload.get('result')[0].get('method').get('id') == method_id
    assert variable_payload.get('result')[0].get('scale').get('id') == scale_id


@pytest.mark.asyncio(scope="session")
async def test_add_layout(client, first_user_login_token, lorem_text_generator):
    layout_name = lorem_text_generator.new_text()
    num_axes = 2
    response = await post_to_add_entry(
        client,
        token=first_user_login_token,
        label="LayoutType",
        name=layout_name,
        description=lorem_text_generator.new_text(20),
        abbreviation=lorem_text_generator.new_text(5),
        synonyms=[lorem_text_generator.new_text(10),lorem_text_generator.new_text(5)],
        axes=num_axes
    )
    assert_payload_success(get_verified_payload(response, "ontology_add_entry"))
    response = await post_to_get_entries(client, token=first_user_login_token, label="LayoutType", name=layout_name)
    layout_payload = get_verified_payload(response, "ontology_entries")
    assert layout_payload.get('result')[0].get('id')
    assert layout_payload.get('result')[0].get('axes') == num_axes
