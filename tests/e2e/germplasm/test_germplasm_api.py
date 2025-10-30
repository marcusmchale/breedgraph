import pytest, pytest_asyncio

from tests.e2e.germplasm.post_methods import (
  post_to_create_germplasm_entry,
  post_to_get_germplasm_entries,
  post_to_get_germplasm_crops,
  post_to_update_germplasm_entry
)

from tests.e2e.utils import get_verified_payload, assert_payload_success

@pytest.mark.usefixtures("session_database")
@pytest.mark.asyncio(scope="session")
async def test_create_crop(
        client,
        first_user_login_token,
        first_account_with_all_affiliations,
):
    germplasm_input = {
        'name': "Coffee"
    }
    response = await post_to_create_germplasm_entry(
        client,
        token=first_user_login_token,
        germplasm_input=germplasm_input
    )
    germplasm_payload = get_verified_payload(response, "germplasmCreateEntry")
    assert_payload_success(germplasm_payload)

@pytest.mark.asyncio(scope="session")
async def test_get_entry(
        client,
        first_user_login_token,
        first_account_with_all_affiliations,
):
    response = await post_to_get_germplasm_entries(
        client,
        token=first_user_login_token,
        names=["Coffee"]
    )
    germplasm_payload = get_verified_payload(response, "germplasmEntries")
    assert_payload_success(germplasm_payload)
    assert germplasm_payload.get('result')

@pytest.mark.asyncio(scope="session")
async def test_get_crops(
        client,
        first_user_login_token,
        first_account_with_all_affiliations,
):
    response = await post_to_get_germplasm_crops(
        client,
        token=first_user_login_token
    )
    germplasm_payload = get_verified_payload(response, "germplasmCrops")
    assert_payload_success(germplasm_payload)
    assert germplasm_payload.get('result')


@pytest.mark.asyncio(scope="session")
async def test_create_crop_same_name_fails(
        client,
        first_user_login_token,
        first_account_with_all_affiliations,
):
    germplasm_input = {
        'name': "Coffee"
    }
    response = await post_to_create_germplasm_entry(
        client,
        token=first_user_login_token,
        germplasm_input=germplasm_input
    )
    germplasm_payload = get_verified_payload(response, "germplasmCreateEntry")
    assert germplasm_payload.get('errors')

@pytest_asyncio.fixture(scope='session')
async def crop_details(client, first_user_login_token, first_account_with_all_affiliations):
    response = await post_to_get_germplasm_crops(
        client,
        token=first_user_login_token
    )
    germplasm_payload = get_verified_payload(response, "germplasmCrops")
    yield germplasm_payload.get('result')[0]

@pytest.mark.asyncio(scope="session")
async def test_create_variety(
        client,
        first_user_login_token,
        first_account_with_all_affiliations,
        crop_details
):
    germplasm_input = {
        'name': "Marsellesa",
        'sources': [ {'sourceId': crop_details.get('id'), 'sourceType': 'UNKNOWN'}]
    }
    response = await post_to_create_germplasm_entry(
        client,
        token=first_user_login_token,
        germplasm_input=germplasm_input
    )
    germplasm_payload = get_verified_payload(response, "germplasmCreateEntry")
    assert_payload_success(germplasm_payload)

@pytest.mark.asyncio(scope="session")
async def test_create_second_variety(
        client,
        first_user_login_token,
        first_account_with_all_affiliations,
        crop_details
):
    germplasm_input = {
        'name': "CIR-SM01",
        'sources': [ {'sourceId': crop_details.get('id'), 'sourceType': 'UNKNOWN'}]
    }
    response = await post_to_create_germplasm_entry(
        client,
        token=first_user_login_token,
        germplasm_input=germplasm_input
    )
    germplasm_payload = get_verified_payload(response, "germplasmCreateEntry")
    assert_payload_success(germplasm_payload)

@pytest.mark.asyncio(scope="session")
async def test_create_hybrid(
        client,
        first_user_login_token,
        first_account_with_all_affiliations,
):
    response = await post_to_get_germplasm_entries(
        client,
        token=first_user_login_token,
        names=["Marsellesa", "CIR-SM01"]
    )
    germplasm_payload = get_verified_payload(response, "germplasmEntries")
    id_map = {record['name']: record['id'] for record in germplasm_payload.get('result')}
    germplasm_input = {
        'name': "Starmaya",
        'sources': [
            {'sourceId': id_map['Marsellesa'], 'sourceType': 'MATERNAL'},
            {'sourceId': id_map['CIR-SM01'], 'sourceType': 'PATERNAL'},
        ]
    }
    response = await post_to_create_germplasm_entry(
        client,
        token=first_user_login_token,
        germplasm_input=germplasm_input
    )
    germplasm_payload = get_verified_payload(response, "germplasmCreateEntry")
    assert_payload_success(germplasm_payload)

    response = await post_to_get_germplasm_entries(
        client,
        token=first_user_login_token,
        names=["Starmaya"]
    )
    germplasm_payload = get_verified_payload(response, "germplasmEntries")
    assert_payload_success(germplasm_payload)
    source_names = [source_rel.get('source').get('name') for source_rel in germplasm_payload.get('result')[0].get('sources')]
    assert 'Marsellesa' in source_names
    assert 'CIR-SM01' in source_names


@pytest.mark.asyncio(scope="session")
async def test_update_variety(
        client,
        first_user_login_token,
        first_account_with_all_affiliations,
):
    response = await post_to_get_germplasm_entries(
        client,
        token=first_user_login_token,
        names=["Starmaya"]
    )
    germplasm_payload = get_verified_payload(response, "germplasmEntries")
    assert_payload_success(germplasm_payload)
    starmaya_id = germplasm_payload.get('result')[0].get('id')
    type_to_id = {
        source_rel.get('sourceType'): source_rel.get('source').get('id')
        for source_rel in germplasm_payload.get('result')[0].get('sources')
    }
    germplasm_input = {
        'id': starmaya_id,
        'name': "Starmaya2",
        'sources':  [
            {'sourceId': type_to_id['PATERNAL'], 'sourceType': 'MATERNAL'},
            {'sourceId': type_to_id['MATERNAL'], 'sourceType': 'PATERNAL'},
        ]
    }
    response = await post_to_update_germplasm_entry(
        client,
        token=first_user_login_token,
        germplasm_input=germplasm_input
    )
    germplasm_payload = get_verified_payload(response, "germplasmUpdateEntry")
    assert_payload_success(germplasm_payload)

    response = await post_to_get_germplasm_entries(
        client,
        token=first_user_login_token,
        names=["Starmaya2"]
    )
    germplasm_payload = get_verified_payload(response, "germplasmEntries")
    assert_payload_success(germplasm_payload)
    updated_type_to_id = {
        source_rel.get('sourceType'): source_rel.get('source').get('id')
        for source_rel in germplasm_payload.get('result')[0].get('sources')
    }
    assert type_to_id['MATERNAL'] == updated_type_to_id['PATERNAL']
    assert type_to_id['PATERNAL'] == updated_type_to_id['MATERNAL']


