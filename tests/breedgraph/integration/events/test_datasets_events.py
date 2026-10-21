import pytest

from breedgraph.domain.events.datasets import DatasetSubmitted
from breedgraph.domain.model.submissions import SubmissionStatus
from breedgraph.service_layer.handlers.events.datasets import handle_dataset_submitted

@pytest.mark.asyncio(loop_scope="session")
async def test_create_dataset_command(
        bus,
        event_queue,
        uow_factory,
        views_factory,
        state_store,
        lorem_text_generator,
        dataset_build_context
):
    user_id: int = dataset_build_context['user_id']
    study_id: int = dataset_build_context['study_id']

    records = [{
        'unit_id': dataset_build_context['unit_id'],
        'value': f'{i * 10}',
        'start': '2010'
    } for i in range(3)]
    records += [{
        'unit_id': dataset_build_context['unit_id'],
        'value': f'{i * 20}',
        'start': '2011'
    } for i in range(3)]

    dataset_input = {
        'study_id': study_id,
        'concept_id': dataset_build_context['concept_id'],
        'records': records
    }
    submission_id = await state_store.store_submission(agent_id=user_id, submission=dataset_input)

    event = DatasetSubmitted(
        agent_id=user_id,
        write_team=dataset_build_context['team_id'],
        submission_id=submission_id
    )
    await bus.handle(event)
    await event_queue.join()

    status = await state_store.get_status(agent_id=user_id, key=submission_id)
    assert status == SubmissionStatus.COMPLETED
    errors = await state_store.get_errors(agent_id=user_id, key=submission_id)
    item_errors = await state_store.get_submission_item_errors(agent_id=user_id, submission_id=submission_id)
    assert not any([errors, item_errors])

    dataset_id = await state_store.get_submission_dataset_id(agent_id=user_id, submission_id=submission_id)
    async with views_factory.get_views(user_id=user_id) as views:
        dataset_summaries = await views.datasets.get_dataset_summaries(study_id=study_id)
        assert dataset_summaries
        for summary in dataset_summaries:
            if summary.id == dataset_id:
                assert summary.concept_id == dataset_build_context['concept_id']
                assert summary.record_count == len(records)
                assert summary.unit_count == 1
                break
        else:
            raise RuntimeError(f'Dataset summary for {dataset_id} not found')






@pytest.mark.asyncio(loop_scope="session")
async def test_citing_an_unreadable_reference_fails_the_submission(
        bus,
        event_queue,
        uow_factory,
        state_store,
        dataset_build_context
):
    from breedgraph.domain.commands.references import CreateExternalReference
    from tests.breedgraph.scenarios.account_builder import AccountBuilder

    other = await AccountBuilder(uow_factory=uow_factory).account_with_affiliations()
    hidden_id = await bus.handle(CreateExternalReference(
        agent_id=other['user_id'], write_team=other['team_id'], url='https://example.org/hidden'
    ))
    user_id: int = dataset_build_context['user_id']
    record = {'unit_id': dataset_build_context['unit_id'], 'value': '1', 'start': '2012'}
    for dataset_input in (
        {'reference_ids': [hidden_id], 'records': [record]},
        {'records': [{**record, 'reference_ids': [hidden_id]}]}
    ):
        submission_id = await state_store.store_submission(agent_id=user_id, submission={
            'study_id': dataset_build_context['study_id'],
            'concept_id': dataset_build_context['concept_id'],
            **dataset_input
        })
        await bus.handle(DatasetSubmitted(agent_id=user_id, write_team=dataset_build_context['team_id'], submission_id=submission_id))
        await event_queue.join()
        assert await state_store.get_status(agent_id=user_id, key=submission_id) == SubmissionStatus.FAILED
        assert 'NoResultFoundError' in str(await state_store.get_errors(agent_id=user_id, key=submission_id))


@pytest.mark.asyncio(loop_scope="session")
async def test_a_reference_cited_by_a_record_keeps_the_release_of_its_dataset(
        bus,
        event_queue,
        uow_factory,
        state_store,
        dataset_build_context
):
    from breedgraph.custom_exceptions import IllegalOperationError
    from breedgraph.domain.commands.controls import SetRelease
    from breedgraph.domain.commands.references import CreateExternalReference
    from breedgraph.domain.model.controls import ControlledModelLabel, ReadRelease

    user_id: int = dataset_build_context['user_id']
    reference_id = await bus.handle(CreateExternalReference(
        agent_id=user_id, write_team=dataset_build_context['team_id'], release=ReadRelease.PUBLIC, url='https://example.org/method'
    ))
    submission_id = await state_store.store_submission(agent_id=user_id, submission={
        'study_id': dataset_build_context['study_id'],
        'concept_id': dataset_build_context['concept_id'],
        'records': [{'unit_id': dataset_build_context['unit_id'], 'value': '1', 'start': '2013', 'reference_ids': [reference_id]}]
    })
    await bus.handle(DatasetSubmitted(
        agent_id=user_id, write_team=dataset_build_context['team_id'], release=ReadRelease.REGISTERED, submission_id=submission_id
    ))
    await event_queue.join()
    assert await state_store.get_status(agent_id=user_id, key=submission_id) == SubmissionStatus.COMPLETED

    def set_release(release):
        return SetRelease(agent_id=user_id, entity_ids=[reference_id], entity_label=ControlledModelLabel.REFERENCE, release=release)
    with pytest.raises(IllegalOperationError):
        await bus.handle(set_release(ReadRelease.PRIVATE))
    await bus.handle(set_release(ReadRelease.REGISTERED))



async def licensed_study(bus, uow_factory, context, name: str, release, licence_release) -> int:
    """A new study in the context's trial, released as given, with a new legal licence released as given"""
    from breedgraph.domain.commands.programs import CreateStudy
    from breedgraph.domain.commands.references import CreateLegalReference

    licence_id = await bus.handle(CreateLegalReference(
        agent_id=context['user_id'], write_team=context['team_id'], release=licence_release, text='Use with attribution'
    ))
    await bus.handle(CreateStudy(
        agent_id=context['user_id'], write_team=context['team_id'], release=release,
        trial_id=context['trial_id'], name=name, licence_id=licence_id
    ))
    async with uow_factory.get_uow(user_id=context['user_id']) as uow:
        program = await uow.repositories.programs.get(trial_id=context['trial_id'])
        return next(study.id for study in program.get_trial(context['trial_id']).studies.values() if study.name == name)


async def submit_dataset(bus, event_queue, state_store, context, study_id: int, release) -> str:
    submission_id = await state_store.store_submission(agent_id=context['user_id'], submission={
        'study_id': study_id,
        'concept_id': context['concept_id'],
        'records': [{'unit_id': context['unit_id'], 'value': '1', 'start': '2014'}]
    })
    await bus.handle(DatasetSubmitted(
        agent_id=context['user_id'], write_team=context['team_id'], release=release, submission_id=submission_id
    ))
    await event_queue.join()
    return submission_id


@pytest.mark.asyncio(loop_scope="session")
async def test_a_dataset_is_not_created_above_the_licence_of_its_study(
        bus,
        event_queue,
        uow_factory,
        views_factory,
        state_store,
        lorem_text_generator,
        dataset_build_context
):
    """docs/read-access.md, rule 10: the check runs as the submission commits, so nothing of the dataset is kept"""
    from breedgraph.domain.model.controls import ReadRelease

    context = dataset_build_context
    user_id = context['user_id']
    study_id = await licensed_study(
        bus, uow_factory, context, lorem_text_generator.new_text(), ReadRelease.REGISTERED, ReadRelease.REGISTERED
    )

    refused = await submit_dataset(bus, event_queue, state_store, context, study_id, ReadRelease.PUBLIC)
    assert await state_store.get_status(agent_id=user_id, key=refused) == SubmissionStatus.FAILED
    assert 'cannot be the licence of data released as PUBLIC' in str(await state_store.get_errors(agent_id=user_id, key=refused))
    async with views_factory.get_views(user_id=user_id) as views:
        assert await views.datasets.get_dataset_summaries(study_id=study_id) == []

    accepted = await submit_dataset(bus, event_queue, state_store, context, study_id, ReadRelease.REGISTERED)
    assert await state_store.get_status(agent_id=user_id, key=accepted) == SubmissionStatus.COMPLETED


@pytest.mark.asyncio(loop_scope="session")
async def test_a_dataset_is_not_moved_into_a_study_with_a_narrower_licence(
        bus,
        event_queue,
        uow_factory,
        state_store,
        lorem_text_generator,
        dataset_build_context
):
    from breedgraph.domain.events.datasets import DatasetUpdateSubmitted
    from breedgraph.domain.model.controls import ReadRelease

    context = dataset_build_context
    user_id = context['user_id']
    submitted = await submit_dataset(bus, event_queue, state_store, context, context['study_id'], ReadRelease.PUBLIC)
    assert await state_store.get_status(agent_id=user_id, key=submitted) == SubmissionStatus.COMPLETED
    dataset_id = await state_store.get_submission_dataset_id(agent_id=user_id, submission_id=submitted)
    target_id = await licensed_study(
        bus, uow_factory, context, lorem_text_generator.new_text(), ReadRelease.PRIVATE, ReadRelease.PRIVATE
    )

    update_id = await state_store.store_submission(agent_id=user_id, submission={'dataset_id': dataset_id, 'study_id': target_id})
    await bus.handle(DatasetUpdateSubmitted(agent_id=user_id, submission_id=update_id))
    await event_queue.join()
    assert await state_store.get_status(agent_id=user_id, key=update_id) == SubmissionStatus.FAILED
    assert 'cannot be the licence of data released as PUBLIC' in str(await state_store.get_errors(agent_id=user_id, key=update_id))
    async with uow_factory.get_uow(user_id=user_id) as uow:
        assert (await uow.repositories.datasets.get(dataset_id=dataset_id)).study == context['study_id']

@pytest.mark.asyncio(loop_scope="session")
async def test_contributions_credit_readable_persons_with_roles(
        bus,
        event_queue,
        uow_factory,
        state_store,
        dataset_build_context
):
    from breedgraph.domain.model.ontology import OntologyEntryLabel
    from tests.breedgraph.scenarios.account_builder import AccountBuilder
    from tests.breedgraph.scenarios.person_builder import PersonBuilder

    user_id: int = dataset_build_context['user_id']
    async with uow_factory.get_uow(user_id=user_id) as uow:
        curation_id = (await uow.ontology.get_entry(name='Data curation', label=OntologyEntryLabel.ROLE)).id

    async def submit(contributions) -> str:
        submission_id = await state_store.store_submission(agent_id=user_id, submission={
            'study_id': dataset_build_context['study_id'],
            'concept_id': dataset_build_context['concept_id'],
            'contributions': contributions
        })
        await bus.handle(DatasetSubmitted(agent_id=user_id, write_team=dataset_build_context['team_id'], submission_id=submission_id))
        await event_queue.join()
        return submission_id

    person_id = dataset_build_context['person_id']
    submission_id = await submit([{'person_id': person_id, 'role_ids': [curation_id]}])
    assert await state_store.get_status(agent_id=user_id, key=submission_id) == SubmissionStatus.COMPLETED
    dataset_id = await state_store.get_submission_dataset_id(agent_id=user_id, submission_id=submission_id)
    async with uow_factory.get_uow(user_id=user_id) as uow:
        dataset = await uow.repositories.datasets.get(dataset_id=dataset_id)
        assert [(c.person, c.roles) for c in dataset.contributions] == [(person_id, [curation_id])]

    # a Person the submitter cannot read, and an entry that is not a Role, are refused
    other = await AccountBuilder(uow_factory=uow_factory).account_with_affiliations()
    hidden_id = await PersonBuilder(uow_factory=uow_factory).person(user_id=other['user_id'], team_id=other['team_id'])
    for contributions in (
        [{'person_id': hidden_id}],
        [{'person_id': person_id, 'role_ids': [dataset_build_context['concept_id']]}]
    ):
        submission_id = await submit(contributions)
        assert await state_store.get_status(agent_id=user_id, key=submission_id) == SubmissionStatus.FAILED
