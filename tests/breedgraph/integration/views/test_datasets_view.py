import pytest, pytest_asyncio

from breedgraph.domain.model.datasets import DatasetInput, DataRecordInput


from typing import Dict

import logging
logger = logging.getLogger(__name__)


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def dataset_with_records(
        uow_factory,
        dataset_build_context
) -> Dict[str, int]:
    user_id = dataset_build_context['user_id']
    concept_id = dataset_build_context['concept_id']
    study_id = dataset_build_context['study_id']
    unit_id = dataset_build_context['unit_id']
    dataset_input = DatasetInput(
        concept=concept_id,
        study=study_id
    )
    async with uow_factory.get_uow(user_id=user_id, write_team=dataset_build_context['team_id']) as uow:
        dataset = await uow.repositories.datasets.create(dataset_input)
        for i in range(10):
            new_record = DataRecordInput(unit=unit_id, value=str(i))
            dataset.records.append(new_record)
        await uow.commit()
    return {
        'user_id': user_id,
        'dataset_id':dataset.id,
        'study_id': study_id
    }

@pytest.mark.asyncio(loop_scope="session")
async def test_get_dataset_summaries(
        views_factory,
        dataset_with_records
):
    user_id = dataset_with_records['user_id']
    async with views_factory.get_views(user_id=user_id) as views:
        summaries = await views.datasets.get_dataset_summaries(study_id=dataset_with_records['study_id'])
        assert summaries, f"Expected dataset summaries for study {dataset_with_records['study_id']}, but got none"



@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def dataset_with_timed_records(uow_factory, dataset_build_context) -> Dict[str, int]:
    """Records timed to different precisions: their periods run from the start of the start to the end of the end"""
    context = dataset_build_context
    unit_id = context['unit_id']
    records = {
        'year': DataRecordInput(unit=unit_id, value='1', start='2021'),
        'morning': DataRecordInput(unit=unit_id, value='2', start='2021-05-03T10:30', end='2021-05-03'),
        'december': DataRecordInput(unit=unit_id, value='3', end='2020-12')
    }
    async with uow_factory.get_uow(user_id=context['user_id'], write_team=context['team_id']) as uow:
        dataset = await uow.repositories.datasets.create(DatasetInput(concept=context['concept_id'], study=context['study_id']))
        for record in records.values():
            dataset.records.append(record)
        await uow.commit()
    return {'user_id': context['user_id'], 'study_id': context['study_id'], 'dataset_id': dataset.id}


async def record_values(views_factory, context, start=None, end=None) -> set:
    async with views_factory.get_views(user_id=context['user_id']) as views:
        records = await views.datasets.get_records(dataset_id=context['dataset_id'], start=start, end=end)
    return {record['value'] for record in records}


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('start, end, values', [
    # an end includes the whole of its period
    (None, '2021', {'1', '2', '3'}),
    (None, '2020-12-15', {'3'}),
    # a record of 2021 may fall in June, so is in a June window
    ('2021-06', '2021-06', {'1'}),
    # a record ending on 2021-05-03 runs to the end of that day
    ('2021-05-03T12:00', None, {'1', '2'}),
    ('2021-05-04', None, {'1'}),
    # a record with only an end runs over the period of its end
    ('2020-12-31', '2020-12-31', {'3'}),
])
async def test_record_windows_take_partial_times_as_periods(views_factory, dataset_with_timed_records, start, end, values):
    assert await record_values(views_factory, dataset_with_timed_records, start, end) == values


@pytest.mark.asyncio(loop_scope="session")
async def test_record_times_keep_their_precision(views_factory, dataset_with_timed_records):
    from numpy import datetime64, datetime_data
    context = dataset_with_timed_records
    async with views_factory.get_views(user_id=context['user_id']) as views:
        records = {record['value']: record for record in await views.datasets.get_records(dataset_id=context['dataset_id'])}
        summaries = await views.datasets.get_dataset_summaries(study_id=context['study_id'])
        # without the unit fields the time range is read from the records alone
        record_summaries = await views.datasets.get_dataset_summaries(study_id=context['study_id'], fields={'start', 'end'})
        dimensions = await views.datasets.get_dimensions(dataset_id=context['dataset_id'])
    morning = records['2']
    assert morning['start'] == datetime64('2021-05-03T10:30') and datetime_data(morning['start'])[0] == 'm'
    assert morning['end'] == datetime64('2021-05-03') and datetime_data(morning['end'])[0] == 'D'

    # the range runs from the first start to the last end, each as entered
    summary = next(summary for summary in summaries if summary.id == context['dataset_id'])
    record_summary = next(summary for summary in record_summaries if summary.id == context['dataset_id'])
    for time_range in (summary, record_summary, dimensions):
        assert str(time_range.start) == '2020-12'
        assert str(time_range.end) == '2021'


def test_times_with_an_offset_are_refused():
    from breedgraph.domain.model.time_descriptors import TimeZoneGivenError
    for time in ('2021-05-03T10:30Z', '2021-05-03T10:30+02:00'):
        with pytest.raises(TimeZoneGivenError):
            DataRecordInput(unit=1, value='1', start=time)
