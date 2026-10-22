import pytest

from breedgraph.custom_exceptions import NoResultFoundError, ProtectedNodeError
from breedgraph.domain.commands.datasets import CreateDataset, UpdateDataset, AddRecords, RemoveRecords
from breedgraph.domain.commands.unit_graphs import DeleteUnit
from breedgraph.domain.events.datasets import DatasetSubmitted
from breedgraph.domain.model import SubmissionStatus

from tests.breedgraph.scenarios.account_builder import AccountBuilder
from tests.breedgraph.scenarios.dataset_builder import DatasetBuilder
from tests.breedgraph.scenarios.unit_graph_builder import UnitGraphBuilder


@pytest.mark.asyncio(loop_scope="session")
async def test_create_dataset_command(
        bus,
        event_queue,
        uow_factory,
        state_store,
        lorem_text_generator,
        dataset_build_context
):
    user_id = dataset_build_context['user_id']
    records = [{
        'unit_id': dataset_build_context['unit_id'],
        'value': f'{i * 10}'
    } for i in range(3)]
    dataset_input = {
        'study_id': dataset_build_context['study_id'],
        'concept_id': dataset_build_context['concept_id'],
        'records': records
    }
    submission_id = await state_store.store_submission(agent_id=user_id, submission=dataset_input)

    cmd = CreateDataset(
        agent_id=user_id,
        write_team=dataset_build_context['team_id'],
        submission_id=submission_id
    )
    await bus.handle_command(cmd)

    assert event_queue.qsize() == 1
    event = event_queue.get_nowait()
    assert isinstance(event, DatasetSubmitted)
    event_queue.task_done()

    submission_data = await state_store.get_submission_data(agent_id=user_id, submission_id=submission_id)
    assert submission_data == dataset_input
    submission_status = await state_store.get_status(agent_id=user_id, key=submission_id)
    assert submission_status == SubmissionStatus.PENDING


@pytest.mark.asyncio(loop_scope="session")
async def test_a_unit_with_records_is_not_deleted(bus, uow_factory, dataset_build_context):
    context = dataset_build_context
    user_id, team_id = context['user_id'], context['team_id']
    unit_id = await UnitGraphBuilder(uow_factory=uow_factory).unit(user_id=user_id, team_id=team_id)
    dataset_id = (await DatasetBuilder(uow_factory=uow_factory).dataset(
        user_id=user_id,
        team_id=team_id,
        concept_id=context['concept_id'],
        study_id=context['study_id'],
        records=[DatasetBuilder.record_input(unit_id=unit_id, value='10')]
    ))['dataset_id']

    # deleting the unit would leave the record without a unit
    with pytest.raises(ProtectedNodeError, match="Records are for this unit"):
        await bus.handle(DeleteUnit(agent_id=user_id, unit_id=unit_id))
    # one who can't read the unit is told it was not found, and learns nothing of the records
    other = await AccountBuilder(uow_factory=uow_factory).account_with_affiliations()
    with pytest.raises(NoResultFoundError):
        await bus.handle(DeleteUnit(agent_id=other['user_id'], unit_id=unit_id))

    # once its records are removed, the unit can go
    async with uow_factory.get_uow(user_id=user_id) as uow:
        dataset = await uow.repositories.datasets.get(dataset_id=dataset_id)
        record_ids = [record.id for record in dataset.records]
    await bus.handle(RemoveRecords(agent_id=user_id, dataset_id=dataset_id, record_ids=record_ids))
    await bus.handle(DeleteUnit(agent_id=user_id, unit_id=unit_id))
    async with uow_factory.get_uow(user_id=user_id) as uow:
        assert await uow.repositories.unit_graphs.get(unit_id=unit_id) is None
