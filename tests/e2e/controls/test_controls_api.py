import pytest

from tests.e2e.controls.post_methods import post_to_set_release, post_to_controllers

from breedgraph.domain.model.controls import ControlledModelLabel, ReadRelease

from tests.e2e.utils import get_verified_payload, assert_payload_success

@pytest.mark.asyncio(loop_scope="session")
async def test_get_controls(
        control_context,
        login_token_factory,
        client
):
    user_id = control_context['user_id']
    login_token = login_token_factory(user_id=user_id)
    location_id = control_context['location_id']
    controllers_response = await post_to_controllers(
        client=client,
        token=login_token,
        entity_label=ControlledModelLabel.LOCATION,
        entity_ids = [location_id]
    )
    controllers_payload = get_verified_payload(controllers_response, "controlsControllers")
    assert_payload_success(controllers_payload)
    assert(controllers_payload.get('result')[0].get('release') == 'PRIVATE')


@pytest.mark.asyncio(loop_scope="session")
async def test_set_controls(
        control_context,
        login_token_factory,
        client
):
    user_id = control_context['user_id']
    login_token = login_token_factory(user_id=user_id)
    location_id = control_context['location_id']

    set_controls_response = await post_to_set_release(
        client=client,
        token=login_token,
        entity_label=ControlledModelLabel.LOCATION,
        entity_ids=[location_id],
        release=ReadRelease.PUBLIC
    )
    set_controls_payload = get_verified_payload(set_controls_response, "controlsSetRelease")
    assert_payload_success(set_controls_payload)

    controllers_response2 = await post_to_controllers(
        client=client,
        token=login_token,
        entity_label=ControlledModelLabel.LOCATION,
        entity_ids=[location_id]
    )
    controllers_payload2 = get_verified_payload(controllers_response2, "controlsControllers")
    assert_payload_success(controllers_payload2)
    assert (controllers_payload2.get('result')[0].get('release') == 'PUBLIC')