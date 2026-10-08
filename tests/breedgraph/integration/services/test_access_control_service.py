import pytest

from breedgraph.custom_exceptions import IllegalOperationError, UnauthorisedOperationError
from breedgraph.domain.commands.control_transfers import (
    OfferControlTransfer, AcceptControlTransfer, RejectControlTransfer, CancelControlTransfer, RenounceControl
)
from breedgraph.domain.events.control_transfers import ControlTransferOffered
from breedgraph.domain.model.control_transfers import ControlledEntity, ControlTransferStatus
from breedgraph.domain.model.controls import ControlledModelLabel, ReadRelease

from tests.breedgraph.scenarios.germplasm_builder import GermplasmBuilder
from tests.breedgraph.scenarios.program_builder import ProgramBuilder


async def create_program(uow_factory, user_id: int, team_id: int) -> ControlledEntity:
    async with uow_factory.get_uow(user_id=user_id, write_team=team_id) as uow:
        program = await uow.repositories.programs.create(ProgramBuilder.program_input())
        await uow.commit()
    return ControlledEntity(label=ControlledModelLabel.PROGRAM, id=program.id)


async def control_teams(uow_factory, entity: ControlledEntity) -> set[int]:
    async with uow_factory.get_uow() as uow:
        controller = await uow.controls.get_controller(entity.label, entity.id)
    return controller.teams


async def offer(uow_factory, context, entities, **kwargs) -> int:
    async with uow_factory.get_uow(user_id=context['user_id_1']) as uow:
        transfer = await uow.controls.offer_transfer(
            entities=entities,
            from_teams={context['team_id_1']},
            recipient_team=context['team_id_2'],
            **kwargs
        )
        await uow.commit()
    return transfer.id


@pytest.mark.asyncio(loop_scope="session")
async def test_offer_and_accept_into_child_team(uow_factory, control_transfer_context):
    program = await create_program(uow_factory, control_transfer_context['user_id_1'], control_transfer_context['team_id_1'])
    transfer_id = await offer(uow_factory, control_transfer_context, [program])

    # Controls do not change until accepted
    assert await control_teams(uow_factory, program) == {control_transfer_context['team_id_1']}

    async with uow_factory.get_uow(user_id=control_transfer_context['user_id_2']) as uow:
        transfer = await uow.controls.accept_transfer(
            transfer_id, to_teams={control_transfer_context['child_team_id']}, release=ReadRelease.REGISTERED
        )
        await uow.commit()
    assert transfer.status is ControlTransferStatus.ACCEPTED
    assert transfer.accepted_at is not None

    assert await control_teams(uow_factory, program) == {control_transfer_context['child_team_id']}
    async with uow_factory.get_uow() as uow:
        controller = await uow.controls.get_controller(program.label, program.id)
    assert controller.release is ReadRelease.REGISTERED


@pytest.mark.asyncio(loop_scope="session")
async def test_offer_raises_event(uow_factory, control_transfer_context):
    program = await create_program(uow_factory, control_transfer_context['user_id_1'], control_transfer_context['team_id_1'])
    async with uow_factory.get_uow(user_id=control_transfer_context['user_id_1']) as uow:
        transfer = await uow.controls.offer_transfer(
            entities=[program], from_teams={control_transfer_context['team_id_1']}, recipient_team=control_transfer_context['team_id_2']
        )
        events = list(uow.controls.collect_events())
    assert events == [ControlTransferOffered(
        transfer_id=transfer.id,
        recipient_team=control_transfer_context['team_id_2'],
        offered_by=control_transfer_context['user_id_1'],
        entity_count=1
    )]


@pytest.mark.asyncio(loop_scope="session")
async def test_transfer_moves_only_the_named_model(uow_factory, control_transfer_context):
    team_id_1 = control_transfer_context['team_id_1']
    async with uow_factory.get_uow(user_id=control_transfer_context['user_id_1'], write_team=team_id_1) as uow:
        program = await uow.repositories.programs.create(ProgramBuilder.program_input())
        program.add_trial(ProgramBuilder.trial_input())
        await uow.commit()
        program_entity = ControlledEntity(label=ControlledModelLabel.PROGRAM, id=program.id)
        trial_entity = ControlledEntity(label=ControlledModelLabel.TRIAL, id=list(program.trials.keys())[0])

    transfer_id = await offer(uow_factory, control_transfer_context, [program_entity])
    async with uow_factory.get_uow(user_id=control_transfer_context['user_id_2']) as uow:
        await uow.controls.accept_transfer(transfer_id, to_teams={control_transfer_context['team_id_2']})
        await uow.commit()

    assert await control_teams(uow_factory, program_entity) == {control_transfer_context['team_id_2']}
    assert await control_teams(uow_factory, trial_entity) == {team_id_1}


@pytest.mark.asyncio(loop_scope="session")
async def test_child_team_admin_cannot_accept_offer_to_root(uow_factory, control_transfer_context):
    program = await create_program(uow_factory, control_transfer_context['user_id_1'], control_transfer_context['team_id_1'])
    transfer_id = await offer(uow_factory, control_transfer_context, [program])

    async with uow_factory.get_uow(user_id=control_transfer_context['user_id_3']) as uow:
        # The transfer is not visible to admins of the child team only
        assert await uow.controls.get_transfer(transfer_id) is None
        with pytest.raises(Exception, match="not found"):
            await uow.controls.accept_transfer(transfer_id, to_teams={control_transfer_context['child_team_id']})

    assert await control_teams(uow_factory, program) == {control_transfer_context['team_id_1']}


@pytest.mark.asyncio(loop_scope="session")
async def test_offer_requires_admin_of_from_teams(uow_factory, control_transfer_context):
    program = await create_program(uow_factory, control_transfer_context['user_id_1'], control_transfer_context['team_id_1'])
    async with uow_factory.get_uow(user_id=control_transfer_context['user_id_2']) as uow:
        with pytest.raises(UnauthorisedOperationError):
            await uow.controls.offer_transfer(
                entities=[program], from_teams={control_transfer_context['team_id_1']}, recipient_team=control_transfer_context['team_id_2']
            )


@pytest.mark.asyncio(loop_scope="session")
async def test_offer_requires_from_teams_to_control_entities(uow_factory, control_transfer_context):
    program = await create_program(uow_factory, control_transfer_context['user_id_2'], control_transfer_context['team_id_2'])
    async with uow_factory.get_uow(user_id=control_transfer_context['user_id_1']) as uow:
        with pytest.raises(IllegalOperationError, match="do not control"):
            await uow.controls.offer_transfer(
                entities=[program], from_teams={control_transfer_context['team_id_1']}, recipient_team=control_transfer_context['team_id_2']
            )


@pytest.mark.asyncio(loop_scope="session")
async def test_immediate_acceptance_for_admin_of_both_sides(uow_factory, control_transfer_context):
    # user 2 administers both the root and the child team of the second organisation
    program = await create_program(uow_factory, control_transfer_context['user_id_2'], control_transfer_context['team_id_2'])
    async with uow_factory.get_uow(user_id=control_transfer_context['user_id_2']) as uow:
        transfer = await uow.controls.offer_transfer(
            entities=[program],
            from_teams={control_transfer_context['team_id_2']},
            recipient_team=control_transfer_context['team_id_2'],
            to_teams={control_transfer_context['child_team_id']}
        )
        events = list(uow.controls.collect_events())
        await uow.commit()

    assert transfer.status is ControlTransferStatus.ACCEPTED
    assert transfer.offered_by == transfer.accepted_by
    assert events == []
    assert await control_teams(uow_factory, program) == {control_transfer_context['child_team_id']}


@pytest.mark.asyncio(loop_scope="session")
async def test_shared_control(uow_factory, control_transfer_context):
    program = await create_program(uow_factory, control_transfer_context['user_id_1'], control_transfer_context['team_id_1'])
    transfer_id = await offer(uow_factory, control_transfer_context, [program], keep_from_teams=True)
    async with uow_factory.get_uow(user_id=control_transfer_context['user_id_2']) as uow:
        await uow.controls.accept_transfer(transfer_id, to_teams={control_transfer_context['team_id_2']})
        await uow.commit()

    assert await control_teams(uow_factory, program) == {control_transfer_context['team_id_1'], control_transfer_context['team_id_2']}

    # either team can then renounce, but not both
    async with uow_factory.get_uow(user_id=control_transfer_context['user_id_1']) as uow:
        await uow.controls.renounce_controls(entities=[program], team_ids={control_transfer_context['team_id_1']})
        await uow.commit()
    assert await control_teams(uow_factory, program) == {control_transfer_context['team_id_2']}

    async with uow_factory.get_uow(user_id=control_transfer_context['user_id_2']) as uow:
        with pytest.raises(IllegalOperationError, match="At least one control team must remain"):
            await uow.controls.renounce_controls(entities=[program], team_ids={control_transfer_context['team_id_2']})


@pytest.mark.asyncio(loop_scope="session")
async def test_renounce_requires_admin(uow_factory, control_transfer_context):
    program = await create_program(uow_factory, control_transfer_context['user_id_1'], control_transfer_context['team_id_1'])
    async with uow_factory.get_uow(user_id=control_transfer_context['user_id_2']) as uow:
        with pytest.raises(UnauthorisedOperationError):
            await uow.controls.renounce_controls(entities=[program], team_ids={control_transfer_context['team_id_1']})


@pytest.mark.asyncio(loop_scope="session")
async def test_reject_and_cancel(uow_factory, control_transfer_context):
    program = await create_program(uow_factory, control_transfer_context['user_id_1'], control_transfer_context['team_id_1'])
    rejected_id = await offer(uow_factory, control_transfer_context, [program])
    cancelled_id = await offer(uow_factory, control_transfer_context, [program])

    async with uow_factory.get_uow(user_id=control_transfer_context['user_id_2']) as uow:
        rejected = await uow.controls.reject_transfer(rejected_id)
        with pytest.raises(UnauthorisedOperationError):
            await uow.controls.cancel_transfer(cancelled_id)
        await uow.commit()
    async with uow_factory.get_uow(user_id=control_transfer_context['user_id_1']) as uow:
        cancelled = await uow.controls.cancel_transfer(cancelled_id)
        await uow.commit()

    assert rejected.status is ControlTransferStatus.REJECTED and rejected.rejected_at is not None
    assert cancelled.status is ControlTransferStatus.CANCELLED and cancelled.cancelled_at is not None
    assert await control_teams(uow_factory, program) == {control_transfer_context['team_id_1']}

    async with uow_factory.get_uow(user_id=control_transfer_context['user_id_2']) as uow:
        with pytest.raises(IllegalOperationError, match="not pending"):
            await uow.controls.accept_transfer(rejected_id, to_teams={control_transfer_context['team_id_2']})


@pytest.mark.asyncio(loop_scope="session")
async def test_acceptance_rechecks_controls(uow_factory, control_transfer_context):
    # The offering team loses control before acceptance, through another accepted transfer
    program = await create_program(uow_factory, control_transfer_context['user_id_1'], control_transfer_context['team_id_1'])
    first_id = await offer(uow_factory, control_transfer_context, [program])
    second_id = await offer(uow_factory, control_transfer_context, [program])
    async with uow_factory.get_uow(user_id=control_transfer_context['user_id_2']) as uow:
        await uow.controls.accept_transfer(first_id, to_teams={control_transfer_context['team_id_2']})
        await uow.commit()

    async with uow_factory.get_uow(user_id=control_transfer_context['user_id_2']) as uow:
        with pytest.raises(IllegalOperationError, match="do not control"):
            await uow.controls.accept_transfer(second_id, to_teams={control_transfer_context['child_team_id']})


@pytest.mark.asyncio(loop_scope="session")
async def test_ended_controls_are_kept_as_history(uow_factory, control_transfer_context):
    program = await create_program(uow_factory, control_transfer_context['user_id_1'], control_transfer_context['team_id_1'])
    transfer_id = await offer(uow_factory, control_transfer_context, [program])
    async with uow_factory.get_uow(user_id=control_transfer_context['user_id_2']) as uow:
        await uow.controls.accept_transfer(transfer_id, to_teams={control_transfer_context['team_id_2']})
        await uow.commit()

    async with uow_factory.get_uow() as uow:
        result = await uow.tx.run(
            "MATCH (:Team {id: $team_id})-[:CONTROLS]->(:TeamPrograms)-[:CONTROLS]->(control:Control)"
            "-[:CONTROLS]->(:Program {id: $program_id}) "
            "RETURN control.ended AS ended ORDER BY control.sequence",
            team_id=control_transfer_context['team_id_1'],
            program_id=program.id
        )
        ended = [record['ended'] async for record in result]
    assert ended == [None, True]


@pytest.mark.asyncio(loop_scope="session")
async def test_get_transfers_for_admins(uow_factory, control_transfer_context):
    program = await create_program(uow_factory, control_transfer_context['user_id_1'], control_transfer_context['team_id_1'])
    transfer_id = await offer(uow_factory, control_transfer_context, [program])

    for user_id in (control_transfer_context['user_id_1'], control_transfer_context['user_id_2']):
        async with uow_factory.get_uow(user_id=user_id) as uow:
            pending = await uow.controls.get_transfers(statuses=[ControlTransferStatus.PENDING])
            assert transfer_id in [transfer.id for transfer in pending]

    async with uow_factory.get_uow(user_id=control_transfer_context['user_id_3']) as uow:
        assert transfer_id not in [transfer.id for transfer in await uow.controls.get_transfers()]


@pytest.mark.asyncio(loop_scope="session")
async def test_germplasm_views_follow_transfer(uow_factory, views_factory, control_transfer_context):
    germplasm_id = await GermplasmBuilder(uow_factory).germplasm(
        user_id=control_transfer_context['user_id_1'], team_id=control_transfer_context['team_id_1']
    )
    germplasm = ControlledEntity(label=ControlledModelLabel.GERMPLASM, id=germplasm_id)
    transfer_id = await offer(uow_factory, control_transfer_context, [germplasm])
    async with uow_factory.get_uow(user_id=control_transfer_context['user_id_2']) as uow:
        await uow.controls.accept_transfer(transfer_id, to_teams={control_transfer_context['team_id_2']})
        await uow.commit()

    async with views_factory.get_views(user_id=control_transfer_context['user_id_1']) as views:
        [entry] = await views.germplasm.get_entries(entry_ids=[germplasm_id])
        assert entry.name == 'REDACTED'
    async with views_factory.get_views(user_id=control_transfer_context['user_id_2']) as views:
        [entry] = await views.germplasm.get_entries(entry_ids=[germplasm_id])
        assert entry.name != 'REDACTED'


@pytest.mark.asyncio(loop_scope="session")
async def test_commands(bus, uow_factory, control_transfer_context):
    program = await create_program(uow_factory, control_transfer_context['user_id_1'], control_transfer_context['team_id_1'])
    await bus.handle(OfferControlTransfer(
        agent_id=control_transfer_context['user_id_1'],
        entities=[program],
        from_teams={control_transfer_context['team_id_1']},
        recipient_team=control_transfer_context['team_id_2'],
        keep_from_teams=True
    ))
    async with uow_factory.get_uow(user_id=control_transfer_context['user_id_2']) as uow:
        transfer_ids = [
            transfer.id for transfer in await uow.controls.get_transfers(statuses=[ControlTransferStatus.PENDING])
            if program in transfer.entities
        ]
    assert len(transfer_ids) == 1

    await bus.handle(AcceptControlTransfer(
        agent_id=control_transfer_context['user_id_2'],
        transfer_id=transfer_ids[0],
        to_teams={control_transfer_context['team_id_2']}
    ))
    assert await control_teams(uow_factory, program) == {control_transfer_context['team_id_1'], control_transfer_context['team_id_2']}

    await bus.handle(RenounceControl(
        agent_id=control_transfer_context['user_id_1'],
        entities=[program],
        team_ids={control_transfer_context['team_id_1']}
    ))
    assert await control_teams(uow_factory, program) == {control_transfer_context['team_id_2']}

    rejected = await offer(uow_factory, control_transfer_context, [
        await create_program(uow_factory, control_transfer_context['user_id_1'], control_transfer_context['team_id_1'])
    ])
    await bus.handle(RejectControlTransfer(agent_id=control_transfer_context['user_id_2'], transfer_id=rejected))
    cancelled = await offer(uow_factory, control_transfer_context, [
        await create_program(uow_factory, control_transfer_context['user_id_1'], control_transfer_context['team_id_1'])
    ])
    await bus.handle(CancelControlTransfer(agent_id=control_transfer_context['user_id_1'], transfer_id=cancelled))

    async with uow_factory.get_uow(user_id=control_transfer_context['user_id_1']) as uow:
        assert (await uow.controls.get_transfer(rejected)).status is ControlTransferStatus.REJECTED
        assert (await uow.controls.get_transfer(cancelled)).status is ControlTransferStatus.CANCELLED


class RecordingNotifications:
    def __init__(self):
        self.sent = []

    async def send(self, recipients, message):
        self.sent.append((recipients, message))


@pytest.mark.asyncio(loop_scope="session")
async def test_offer_notifies_recipient_team_admins(uow_factory, control_transfer_context):
    from breedgraph.service_layer.handlers.events.control_transfers import notify_control_transfer_offered

    notifications = RecordingNotifications()
    await notify_control_transfer_offered(
        ControlTransferOffered(
            transfer_id=1,
            recipient_team=control_transfer_context['team_id_2'],
            offered_by=control_transfer_context['user_id_1'],
            entity_count=2
        ),
        uow_factory=uow_factory,
        notifications=notifications
    )

    [(recipients, message)] = notifications.sent
    # Admins of the recipient team only, not admins of the child team
    assert {user.id for user in recipients} == {control_transfer_context['user_id_2']}
    assert 'control transfer offered' in message.message['Subject']
    assert 'offered control of 2 entries' in message.message.get_content()
