"""
A study's licence is a legal reference released at least as widely as the study, every dataset of the study and every
file they or their records cite (docs/read-access.md, rule 10). The rule is checked as the unit of work commits, on the
releases that result.
"""
import uuid

import pytest

from breedgraph.custom_exceptions import IllegalOperationError
from breedgraph.domain.commands.controls import SetRelease
from breedgraph.domain.commands.programs import CreateStudy, UpdateStudy
from breedgraph.domain.commands.references import CreateLegalReference, CreateExternalReference
from breedgraph.domain.model.controls import ControlledModelLabel, ReadRelease
from breedgraph.domain.model.datasets import DatasetInput, DataRecordInput
from breedgraph.domain.model.references import FileReferenceInput

from tests.breedgraph.scenarios.dataset_builder import DatasetBuilder


async def legal_reference(bus, context, release: ReadRelease) -> int:
    return await bus.handle(CreateLegalReference(
        agent_id=context['user_id'], write_team=context['team_id'], release=release,
        description='Licence', text='Use with attribution'
    ))


async def study_ids_named(uow_factory, context, name: str) -> list[int]:
    async with uow_factory.get_uow(user_id=context['user_id']) as uow:
        program = await uow.repositories.programs.get(trial_id=context['trial_id'])
        return [study.id for study in program.get_trial(context['trial_id']).studies.values() if study.name == name]


async def create_study(bus, uow_factory, context, name: str, release: ReadRelease, licence_id: int | None = None) -> int:
    await bus.handle(CreateStudy(
        agent_id=context['user_id'], write_team=context['team_id'], release=release,
        trial_id=context['trial_id'], name=name, licence_id=licence_id
    ))
    return (await study_ids_named(uow_factory, context, name))[0]


async def create_dataset(uow_factory, context, study_id: int, release: ReadRelease) -> int:
    async with uow_factory.get_uow(user_id=context['user_id'], write_team=context['team_id'], release=release) as uow:
        dataset = await uow.repositories.datasets.create(
            DatasetBuilder.dataset_input(concept_id=context['concept_id'], study_id=study_id)
        )
        await uow.commit()
        return dataset.id


async def release_of(uow_factory, label: ControlledModelLabel, model_id: int) -> ReadRelease:
    async with uow_factory.get_uow() as uow:
        return (await uow.controls.get_controller(label, model_id)).release


async def licence_of(uow_factory, context, study_id: int) -> int | None:
    async with uow_factory.get_uow(user_id=context['user_id']) as uow:
        program = await uow.repositories.programs.get(study_id=study_id)
        return program.get_study(study_id).licence_id


def set_release(context, label: ControlledModelLabel, model_id: int, release: ReadRelease) -> SetRelease:
    return SetRelease(agent_id=context['user_id'], entity_ids=[model_id], entity_label=label, release=release)


@pytest.mark.asyncio(loop_scope="session")
async def test_a_licence_must_be_a_legal_reference(bus, uow_factory, dataset_build_context, lorem_text_generator):
    context = dataset_build_context
    external_id = await bus.handle(CreateExternalReference(
        agent_id=context['user_id'], write_team=context['team_id'], url='https://example.org/licence'
    ))
    name = lorem_text_generator.new_text()
    with pytest.raises(IllegalOperationError, match="not a legal reference"):
        await bus.handle(CreateStudy(
            agent_id=context['user_id'], write_team=context['team_id'],
            trial_id=context['trial_id'], name=name, licence_id=external_id
        ))
    assert await study_ids_named(uow_factory, context, name) == []

    study_id = await create_study(bus, uow_factory, context, name, ReadRelease.PRIVATE)
    with pytest.raises(IllegalOperationError, match="not a legal reference"):
        await bus.handle(UpdateStudy(agent_id=context['user_id'], study_id=study_id, licence_id=external_id))
    assert await licence_of(uow_factory, context, study_id) is None


@pytest.mark.asyncio(loop_scope="session")
async def test_a_study_cannot_be_released_more_widely_than_its_licence(bus, uow_factory, dataset_build_context, lorem_text_generator):
    context = dataset_build_context
    licence_id = await legal_reference(bus, context, ReadRelease.REGISTERED)

    name = lorem_text_generator.new_text()
    with pytest.raises(IllegalOperationError, match=f"Reference {licence_id} is released as REGISTERED"):
        await create_study(bus, uow_factory, context, name, ReadRelease.PUBLIC, licence_id)
    assert await study_ids_named(uow_factory, context, name) == []

    study_id = await create_study(bus, uow_factory, context, name, ReadRelease.REGISTERED, licence_id)
    assert await licence_of(uow_factory, context, study_id) == licence_id


@pytest.mark.asyncio(loop_scope="session")
async def test_a_licence_must_be_released_as_widely_as_the_datasets_of_its_study(bus, uow_factory, dataset_build_context, lorem_text_generator):
    context = dataset_build_context
    # a public dataset needs its study to have a licence (docs/licences.md §1)
    first_id = await legal_reference(bus, context, ReadRelease.PUBLIC)
    study_id = await create_study(bus, uow_factory, context, lorem_text_generator.new_text(), ReadRelease.PRIVATE, first_id)
    await create_dataset(uow_factory, context, study_id, ReadRelease.PUBLIC)

    registered_id = await legal_reference(bus, context, ReadRelease.REGISTERED)
    with pytest.raises(IllegalOperationError, match="cannot be the licence of data released as PUBLIC"):
        await bus.handle(UpdateStudy(agent_id=context['user_id'], study_id=study_id, licence_id=registered_id))
    assert await licence_of(uow_factory, context, study_id) == first_id

    public_id = await legal_reference(bus, context, ReadRelease.PUBLIC)
    await bus.handle(UpdateStudy(agent_id=context['user_id'], study_id=study_id, licence_id=public_id))
    assert await licence_of(uow_factory, context, study_id) == public_id


@pytest.mark.asyncio(loop_scope="session")
async def test_a_study_or_its_dataset_cannot_be_released_beyond_its_licence(bus, uow_factory, dataset_build_context, lorem_text_generator):
    context = dataset_build_context
    licence_id = await legal_reference(bus, context, ReadRelease.REGISTERED)
    study_id = await create_study(bus, uow_factory, context, lorem_text_generator.new_text(), ReadRelease.REGISTERED, licence_id)
    dataset_id = await create_dataset(uow_factory, context, study_id, ReadRelease.PRIVATE)

    with pytest.raises(IllegalOperationError, match="cannot be the licence of data released as PUBLIC"):
        await bus.handle(set_release(context, ControlledModelLabel.STUDY, study_id, ReadRelease.PUBLIC))
    assert await release_of(uow_factory, ControlledModelLabel.STUDY, study_id) == ReadRelease.REGISTERED

    with pytest.raises(IllegalOperationError, match="cannot be the licence of data released as PUBLIC"):
        await bus.handle(set_release(context, ControlledModelLabel.DATASET, dataset_id, ReadRelease.PUBLIC))
    assert await release_of(uow_factory, ControlledModelLabel.DATASET, dataset_id) == ReadRelease.PRIVATE

    await bus.handle(set_release(context, ControlledModelLabel.DATASET, dataset_id, ReadRelease.REGISTERED))
    assert await release_of(uow_factory, ControlledModelLabel.DATASET, dataset_id) == ReadRelease.REGISTERED

    # nor can a dataset be created more widely released than the study's licence
    with pytest.raises(IllegalOperationError, match="cannot be the licence of data released as PUBLIC"):
        await create_dataset(uow_factory, context, study_id, ReadRelease.PUBLIC)


@pytest.mark.asyncio(loop_scope="session")
async def test_a_licence_cannot_be_released_below_the_datasets_of_its_study(bus, uow_factory, dataset_build_context, lorem_text_generator):
    context = dataset_build_context
    licence_id = await legal_reference(bus, context, ReadRelease.PUBLIC)
    # a private study alone would not hold its licence's release up (the release floor); its public dataset does
    study_id = await create_study(bus, uow_factory, context, lorem_text_generator.new_text(), ReadRelease.PRIVATE, licence_id)
    await create_dataset(uow_factory, context, study_id, ReadRelease.PUBLIC)

    with pytest.raises(IllegalOperationError, match=f"Reference {licence_id} is the licence of data released as PUBLIC"):
        await bus.handle(set_release(context, ControlledModelLabel.REFERENCE, licence_id, ReadRelease.REGISTERED))
    assert await release_of(uow_factory, ControlledModelLabel.REFERENCE, licence_id) == ReadRelease.PUBLIC


async def dataset_citing_a_file(uow_factory, context, study_id: int, release: ReadRelease, file_release: ReadRelease):
    """A dataset of the study, released as given, whose record cites a new data file released as given: their ids"""
    async with uow_factory.get_uow(user_id=context['user_id'], write_team=context['team_id'], release=file_release) as uow:
        data_file = await uow.repositories.references.create(FileReferenceInput(
            description='Raw data', filename='raw.csv', content_type='text/csv', file_id=uuid.uuid4().hex
        ))
        await uow.commit()
    async with uow_factory.get_uow(user_id=context['user_id'], write_team=context['team_id'], release=release) as uow:
        dataset = await uow.repositories.datasets.create(DatasetInput(
            concept=context['concept_id'], study=study_id,
            records=[DataRecordInput(unit_id=context['unit_id'], value='12', reference_ids=[data_file.id])]
        ))
        await uow.commit()
    return dataset.id, data_file.id


@pytest.mark.asyncio(loop_scope="session")
async def test_a_file_cited_by_licensed_data_is_not_released_beyond_its_licence(bus, uow_factory, dataset_build_context, lorem_text_generator):
    """A private dataset's file read by registered users holds the dataset's data: they can read its licence"""
    context = dataset_build_context
    licence_id = await legal_reference(bus, context, ReadRelease.REGISTERED)
    study_id = await create_study(bus, uow_factory, context, lorem_text_generator.new_text(), ReadRelease.PRIVATE, licence_id)

    with pytest.raises(IllegalOperationError, match="is cited by data under licence"):
        await dataset_citing_a_file(uow_factory, context, study_id, ReadRelease.PRIVATE, ReadRelease.PUBLIC)
    dataset_id, file_id = await dataset_citing_a_file(uow_factory, context, study_id, ReadRelease.PRIVATE, ReadRelease.REGISTERED)

    with pytest.raises(
            IllegalOperationError,
            match=f"Reference {file_id}, released as PUBLIC, is cited by data under licence {licence_id}, released as REGISTERED"
    ):
        await bus.handle(set_release(context, ControlledModelLabel.REFERENCE, file_id, ReadRelease.PUBLIC))
    assert await release_of(uow_factory, ControlledModelLabel.REFERENCE, file_id) == ReadRelease.REGISTERED

    # the licence holds the file's release up, though the study and its dataset are private
    with pytest.raises(IllegalOperationError, match=f"Reference {licence_id} is the licence of data citing a file released as REGISTERED"):
        await bus.handle(set_release(context, ControlledModelLabel.REFERENCE, licence_id, ReadRelease.PRIVATE))
    assert await release_of(uow_factory, ControlledModelLabel.REFERENCE, licence_id) == ReadRelease.REGISTERED

    # released as widely, the licence lets the file be
    await bus.handle(set_release(context, ControlledModelLabel.REFERENCE, licence_id, ReadRelease.PUBLIC))
    await bus.handle(set_release(context, ControlledModelLabel.REFERENCE, file_id, ReadRelease.PUBLIC))
    assert await release_of(uow_factory, ControlledModelLabel.REFERENCE, file_id) == ReadRelease.PUBLIC
