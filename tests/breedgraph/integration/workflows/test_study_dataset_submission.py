import pytest

from breedgraph.domain.model.programs import DatasetScope
from breedgraph.domain.model.ontology import ScaleStored, OntologyEntryLabel
from breedgraph.domain.model.datasets import RecordGroup
from breedgraph.domain.model.submissions import SubmissionStatus

from breedgraph.domain.commands.datasets import CreateDataset
from breedgraph.domain.commands.programs import MergeDatasetScope

from tests.breedgraph.scenarios.program_builder import ProgramBuilder
from tests.breedgraph.scenarios.ontology_builder import OntologyBuilder
from tests.breedgraph.scenarios.dataset_builder import DatasetBuilder
from tests.breedgraph.scenarios.block_builder import BlockBuilder


@pytest.mark.asyncio(loop_scope="session")
async def test_submit_datasets_with_shared_grouping_scopes(
        bus,
        event_queue,
        state_store,
        uow_factory,
        dataset_build_context):

    user_id: int = dataset_build_context['user_id']
    study_id: int = dataset_build_context['study_id']
    grouping_ids: list[int] = dataset_build_context['grouping_ids']
    grouping_names: list[int] = dataset_build_context['grouping_names']
    batch_grouping_name = 'Study Scoped Batch'
    replicate_grouping_name = 'Dataset Scoped Replicate'
    batch_grouping_index = grouping_names.index(batch_grouping_name)
    replicate_grouping_index = grouping_names.index(replicate_grouping_name)
    batch_grouping_id = grouping_ids[batch_grouping_index]
    replicate_grouping_id = grouping_ids[replicate_grouping_index]

    unit_id = await BlockBuilder(uow_factory=uow_factory).unit(user_id=user_id)

    variable1_ids = await OntologyBuilder(uow_factory=uow_factory).variable(user_id=user_id)
    variable2_ids = await OntologyBuilder(uow_factory=uow_factory).variable(user_id=user_id)

    dataset1_input = {
        'study_id': study_id,
        'concept_id': variable1_ids['ontology_variable'],
        'records': [
            {
                'unit_id': unit_id,
                'value': str(i * 100),
                'groups': [
                    {'id': batch_grouping_id, 'code': 'batch 1'},
                    {'id': replicate_grouping_id, 'code': f'R{i + 1}'}
                ]
            }
            for i in range(3)
        ]
    }
    key1 = await state_store.store_submission(agent_id=user_id, submission=dataset1_input)
    cmd1 = CreateDataset(agent_id=user_id, submission_id=key1)
    dataset2_input = {
        'study_id': study_id,
        'concept_id': variable2_ids['ontology_variable'],
        'records': [
            {
                'unit_id': unit_id,
                'value': str(i * 10),
                'groups': [
                    {'id': batch_grouping_id, 'code': 'batch 1'},
                    {'id': replicate_grouping_id, 'code': f'R{i + 1}'}
                ]
            }
            for i in range(3)
        ]
    }
    key2 = await state_store.store_submission(agent_id=user_id, submission=dataset2_input)
    cmd2 = CreateDataset(agent_id=user_id, submission_id=key2)
    #
    await bus.handle(cmd1)
    await bus.handle(cmd2)
    # wait for the submissions to be processed
    await event_queue.join()
    assert await state_store.get_status(agent_id=user_id, key=key1) == SubmissionStatus.COMPLETED
    assert await state_store.get_status(agent_id=user_id, key=key2) == SubmissionStatus.COMPLETED
    # get the dataset ids
    dataset1_id = await state_store.get_submission_dataset_id(agent_id=user_id, submission_id=key1)
    dataset2_id = await state_store.get_submission_dataset_id(agent_id=user_id, submission_id=key2)
    if dataset1_id is None or dataset2_id is None:
        raise ValueError("Dataset IDs are None")

    # then update the grouping scope
    merge_scope_cmd = MergeDatasetScope(
        agent_id = user_id,
        grouping_id=replicate_grouping_id,
        dataset_ids={dataset1_id, dataset2_id}
    )
    await bus.handle(merge_scope_cmd)
