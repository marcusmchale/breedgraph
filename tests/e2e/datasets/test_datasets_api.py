import pytest

from tests.e2e.datasets.post_methods import post_to_add_dataset, post_to_get_datasets, post_to_add_record
from tests.e2e.ontologies.post_methods import post_to_get_entries
from tests.e2e.payload_helpers import get_verified_payload, assert_payload_success

@pytest.mark.usefixtures("session_database")
@pytest.mark.asyncio(scope="session")
async def test_create_dataset(
        client,
        first_user_login_token,
        first_account_with_all_affiliations,
        basic_ontology
):
    variable_response = await post_to_get_entries(
        client,
        token=first_user_login_token,
        label="Variable"
    )
    variable_payload = get_verified_payload(variable_response, "ontology_entries")
    variable_id = variable_payload.get('result')[0].get('id')
    response = await post_to_add_dataset(client, first_user_login_token, term=variable_id)
    payload = get_verified_payload(response, "data_add_dataset")
    assert payload['result']

@pytest.mark.asyncio(scope="session")
async def test_extend_dataset(
        client,
        first_user_login_token,
        first_account_with_all_affiliations,
        basic_ontology,
        basic_block
):

    datasets_response = await post_to_get_datasets(
        client,
        token=first_user_login_token,
        dataset_id=None,
        term_id=None
    )
    datasets_payload = get_verified_payload(datasets_response, 'datasets')
    dataset_id = datasets_payload.get('result')[0].get('id')
    add_record_response = await post_to_add_record(
        client,
        token=first_user_login_token,
        record= {
            'dataset':dataset_id,
            'unit': basic_block.get_root_id(),
            'value': '100',
            'start': "2023-10-10"
        }
    )
    add_record_payload = get_verified_payload(add_record_response, "data_add_record")
    assert_payload_success(add_record_payload)

@pytest.mark.asyncio(scope="session")
async def test_germplasm_dataset(
        client,
        first_user_login_token,
        first_account_with_all_affiliations,
        basic_ontology,
        basic_block,
        basic_germplasm
):
    # todo create basic germplasm
    # todo here create dataset then extend with value
    # test with special characters and both names and IDs


    tree_subject = basic_ontology.get_entry_model("Tree", label="Subject")
    tree_unit_id = [i for i in basic_block.yield_unit_ids_by_subject(tree_subject.id)][0]
    add_record_response = await post_to_add_record(
        client,
        token=first_user_login_token,
        record={
            #'dataset': dataset_id,
            'unit': tree_unit_id,
            'value': '1',
            'start': "2023-10-10"
        }
    )
    import pdb; pdb.set_trace()
    # todo create basic germplasm
    add_record_payload = get_verified_payload(add_record_response, "data_add_record")
