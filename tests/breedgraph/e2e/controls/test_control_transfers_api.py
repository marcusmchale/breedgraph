import pytest

from breedgraph.domain.model.controls import ControlledModelLabel, ReadRelease
from breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus

from tests.breedgraph.e2e.controls.post_methods import (
    post_to_offer_transfer, post_to_accept_transfer, post_to_reject_transfer, post_to_cancel_transfer,
    post_to_renounce_control, post_to_transfers, post_to_transfer, post_to_controllers
)
from tests.breedgraph.e2e.utils import get_verified_payload, assert_payload_success
from tests.breedgraph.scenarios.program_builder import ProgramBuilder


async def create_program(uow_factory, user_id: int, team_id: int) -> int:
    async with uow_factory.get_uow(user_id=user_id, write_team=team_id) as uow:
        program = await uow.repositories.programs.create(ProgramBuilder.program_input())
        await uow.commit()
    return program.id


async def offer_program(client, token, context, program_id: int, **offer) -> int:
    response = await post_to_offer_transfer(client, token, {
        "entities": [{"label": "PROGRAM", "id": program_id}],
        "fromTeamIds": [context['team_id_1']],
        "recipientTeamId": context['team_id_2'],
        **offer
    })
    assert_payload_success(get_verified_payload(response, "controlsOfferTransfer"))

    payload = get_verified_payload(await post_to_transfers(client, token, ["PENDING"]), "controlsTransfers")
    assert_payload_success(payload)
    [transfer] = [
        t for t in payload['result']
        if {"label": "PROGRAM", "id": str(program_id)} in t['entities']
    ]
    return int(transfer['id'])


async def program_control_team_ids(client, token, program_id: int) -> set[int]:
    payload = get_verified_payload(
        await post_to_controllers(client, token, ControlledModelLabel.PROGRAM, [program_id]),
        "controlsControllers"
    )
    assert_payload_success(payload)
    return {int(team['id']) for team in payload['result'][0]['teams']}


@pytest.mark.asyncio(loop_scope="session")
async def test_offer_and_accept(client, login_token_factory, uow_factory, control_transfer_context):
    context = control_transfer_context
    token_1 = login_token_factory(user_id=context['user_id_1'])
    token_2 = login_token_factory(user_id=context['user_id_2'])
    program_id = await create_program(uow_factory, context['user_id_1'], context['team_id_1'])
    transfer_id = await offer_program(client, token_1, context, program_id)

    payload = get_verified_payload(await post_to_transfer(client, token_2, transfer_id), "controlsTransfer")
    assert_payload_success(payload)
    transfer = payload['result']
    assert transfer['status'] == 'PENDING'
    assert transfer['entities'] == [{"label": "PROGRAM", "id": str(program_id)}]
    assert [int(team['id']) for team in transfer['fromTeams']] == [context['team_id_1']]
    assert int(transfer['recipientTeam']['id']) == context['team_id_2']
    assert transfer['toTeams'] == []
    assert transfer['offeredAt'] is not None

    payload = get_verified_payload(
        await post_to_accept_transfer(client, token_2, transfer_id, [context['child_team_id']], ReadRelease.REGISTERED),
        "controlsAcceptTransfer"
    )
    assert_payload_success(payload)

    payload = get_verified_payload(await post_to_transfer(client, token_2, transfer_id), "controlsTransfer")
    transfer = payload['result']
    assert transfer['status'] == 'ACCEPTED'
    assert [int(team['id']) for team in transfer['toTeams']] == [context['child_team_id']]
    assert transfer['release'] == 'REGISTERED'
    assert transfer['acceptedAt'] is not None

    assert await program_control_team_ids(client, token_2, program_id) == {context['child_team_id']}


@pytest.mark.asyncio(loop_scope="session")
async def test_child_team_admin_cannot_accept(client, login_token_factory, uow_factory, control_transfer_context):
    context = control_transfer_context
    token_1 = login_token_factory(user_id=context['user_id_1'])
    token_3 = login_token_factory(user_id=context['user_id_3'])
    program_id = await create_program(uow_factory, context['user_id_1'], context['team_id_1'])
    transfer_id = await offer_program(client, token_1, context, program_id)

    payload = get_verified_payload(await post_to_transfer(client, token_3, transfer_id), "controlsTransfer")
    assert payload['status'] == GQLStatus.ERROR.name

    payload = get_verified_payload(
        await post_to_accept_transfer(client, token_3, transfer_id, [context['child_team_id']]),
        "controlsAcceptTransfer"
    )
    assert payload['status'] == GQLStatus.ERROR.name
    assert await program_control_team_ids(client, token_1, program_id) == {context['team_id_1']}


@pytest.mark.asyncio(loop_scope="session")
async def test_reject_and_cancel(client, login_token_factory, uow_factory, control_transfer_context):
    context = control_transfer_context
    token_1 = login_token_factory(user_id=context['user_id_1'])
    token_2 = login_token_factory(user_id=context['user_id_2'])
    rejected_id = await offer_program(
        client, token_1, context, await create_program(uow_factory, context['user_id_1'], context['team_id_1'])
    )
    cancelled_id = await offer_program(
        client, token_1, context, await create_program(uow_factory, context['user_id_1'], context['team_id_1'])
    )

    assert_payload_success(get_verified_payload(await post_to_reject_transfer(client, token_2, rejected_id), "controlsRejectTransfer"))
    assert_payload_success(get_verified_payload(await post_to_cancel_transfer(client, token_1, cancelled_id), "controlsCancelTransfer"))

    payload = get_verified_payload(await post_to_transfers(client, token_1, ["REJECTED", "CANCELLED"]), "controlsTransfers")
    statuses = {int(t['id']): t['status'] for t in payload['result']}
    assert statuses[rejected_id] == 'REJECTED'
    assert statuses[cancelled_id] == 'CANCELLED'


@pytest.mark.asyncio(loop_scope="session")
async def test_shared_control_and_renounce(client, login_token_factory, uow_factory, control_transfer_context):
    context = control_transfer_context
    token_1 = login_token_factory(user_id=context['user_id_1'])
    token_2 = login_token_factory(user_id=context['user_id_2'])
    program_id = await create_program(uow_factory, context['user_id_1'], context['team_id_1'])
    transfer_id = await offer_program(client, token_1, context, program_id, keepFromTeams=True)
    assert_payload_success(get_verified_payload(
        await post_to_accept_transfer(client, token_2, transfer_id, [context['team_id_2']]), "controlsAcceptTransfer"
    ))
    assert await program_control_team_ids(client, token_1, program_id) == {context['team_id_1'], context['team_id_2']}

    payload = get_verified_payload(
        await post_to_renounce_control(client, token_1, [{"label": "PROGRAM", "id": program_id}], [context['team_id_1']]),
        "controlsRenounceControl"
    )
    assert_payload_success(payload)
    assert await program_control_team_ids(client, token_2, program_id) == {context['team_id_2']}
