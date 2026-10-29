"""
A study, and its datasets, can be released beyond the teams that hold them only once the study has a licence
(docs/read-access.md, rule 10; docs/licences.md §1). The rule is checked as the unit of work commits, on the releases
that result, and the refusal names the study by id. Private studies and datasets need none, and the files their data
cites are not held to it until the study has one.
"""
import pytest

from breedgraph.custom_exceptions import IllegalOperationError
from breedgraph.domain.model.controls import ControlledModelLabel, ReadRelease
from breedgraph.domain.model.datasets import DatasetInput
from breedgraph.domain.model.programs import StudyInput
from breedgraph.service_layer.application.licence_seed import CC_BY

from tests.breedgraph.scenarios.ontology_builder import OntologyBuilder
from tests.breedgraph.scenarios.program_builder import ProgramBuilder
from tests.breedgraph.scenarios.reference_builder import ReferenceBuilder

STUDY = ControlledModelLabel.STUDY
DATASET = ControlledModelLabel.DATASET
NO_LICENCE = "has no licence: a study, and its datasets, can be released"


async def private_study(uow_factory, context, licence_id: int | None = None) -> int:
    async with uow_factory.get_uow(user_id=context['user_id_1'], write_team=context['team_id_1']) as uow:
        program = await uow.repositories.programs.create(ProgramBuilder.program_input())
        program.add_trial(ProgramBuilder.trial_input())
        await uow.repositories.programs.update_seen()
        trial_id = list(program.trials.keys())[0]
        program.add_study(trial_id=trial_id, study=StudyInput(name=ProgramBuilder.program_input().name, licence_id=licence_id))
        await uow.repositories.programs.update_seen()
        study_id = list(program.get_trial(trial_id).studies.keys())[0]
        await uow.commit()
    return study_id


async def standard_licence(uow_factory) -> int:
    async with uow_factory.get_uow() as uow:
        return await uow.repositories.references.get_seeded_id(CC_BY)


async def set_release(uow_factory, context, label, entity_id, release):
    async with uow_factory.get_uow(user_id=context['user_id_1']) as uow:
        await uow.controls.set_controls_by_id_and_label(
            ids=[entity_id], label=label, control_teams={context['team_id_1']}, release=release
        )
        await uow.commit()


async def release_of(uow_factory, label, entity_id) -> ReadRelease:
    async with uow_factory.get_uow() as uow:
        return (await uow.controls.get_controller(label, entity_id)).release


async def variable(uow_factory, context) -> int:
    return (await OntologyBuilder(uow_factory).variable(user_id=context['user_id_1']))['ontology_variable']


async def dataset(uow_factory, context, study_id, concept_id, release=ReadRelease.PRIVATE, reference_ids=None) -> int:
    async with uow_factory.get_uow(user_id=context['user_id_1'], write_team=context['team_id_1'], release=release) as uow:
        stored = await uow.repositories.datasets.create(
            DatasetInput(concept=concept_id, study=study_id, records=[], reference_ids=reference_ids or [])
        )
        await uow.commit()
    return stored.id


@pytest.mark.asyncio(loop_scope="session")
async def test_a_study_without_a_licence_stays_private(uow_factory, control_transfer_context):
    context = control_transfer_context
    study_id = await private_study(uow_factory, context)
    for release in (ReadRelease.REGISTERED, ReadRelease.PUBLIC):
        with pytest.raises(IllegalOperationError, match=f"Study {study_id} {NO_LICENCE}"):
            await set_release(uow_factory, context, STUDY, study_id, release)
    assert await release_of(uow_factory, STUDY, study_id) is ReadRelease.PRIVATE


@pytest.mark.asyncio(loop_scope="session")
async def test_the_datasets_of_a_study_without_a_licence_stay_private(uow_factory, control_transfer_context):
    context = control_transfer_context
    study_id = await private_study(uow_factory, context)
    concept_id = await variable(uow_factory, context)
    dataset_id = await dataset(uow_factory, context, study_id, concept_id)
    with pytest.raises(IllegalOperationError, match=f"Study {study_id} {NO_LICENCE}"):
        await set_release(uow_factory, context, DATASET, dataset_id, ReadRelease.REGISTERED)
    assert await release_of(uow_factory, DATASET, dataset_id) is ReadRelease.PRIVATE
    # nor can one be created released
    with pytest.raises(IllegalOperationError, match=f"Study {study_id} {NO_LICENCE}"):
        await dataset(uow_factory, context, study_id, concept_id, release=ReadRelease.REGISTERED)


@pytest.mark.asyncio(loop_scope="session")
async def test_a_study_with_a_licence_and_its_datasets_can_be_released(uow_factory, control_transfer_context):
    context = control_transfer_context
    study_id = await private_study(uow_factory, context, licence_id=await standard_licence(uow_factory))
    concept_id = await variable(uow_factory, context)
    dataset_id = await dataset(uow_factory, context, study_id, concept_id, release=ReadRelease.PUBLIC)
    await set_release(uow_factory, context, STUDY, study_id, ReadRelease.PUBLIC)
    assert await release_of(uow_factory, STUDY, study_id) is ReadRelease.PUBLIC
    assert await release_of(uow_factory, DATASET, dataset_id) is ReadRelease.PUBLIC


@pytest.mark.asyncio(loop_scope="session")
async def test_the_licence_of_a_released_study_cant_be_removed(uow_factory, control_transfer_context):
    context = control_transfer_context
    study_id = await private_study(uow_factory, context, licence_id=await standard_licence(uow_factory))
    await set_release(uow_factory, context, STUDY, study_id, ReadRelease.REGISTERED)
    async with uow_factory.get_uow(user_id=context['user_id_1']) as uow:
        program = await uow.repositories.programs.get(study_id=study_id)
        program.get_study(study_id).licence_id = None
        with pytest.raises(IllegalOperationError, match=f"Study {study_id} {NO_LICENCE}"):
            await uow.commit()
    # back to private, it can go
    await set_release(uow_factory, context, STUDY, study_id, ReadRelease.PRIVATE)
    async with uow_factory.get_uow(user_id=context['user_id_1']) as uow:
        program = await uow.repositories.programs.get(study_id=study_id)
        program.get_study(study_id).licence_id = None
        await uow.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_files_a_private_study_cites_can_be_released(uow_factory, control_transfer_context):
    """Files the data cites are not a trigger: another team's file cited by a hidden private study is its own"""
    context = control_transfer_context
    study_id = await private_study(uow_factory, context)
    concept_id = await variable(uow_factory, context)
    async with uow_factory.get_uow(user_id=context['user_id_1'], write_team=context['team_id_1']) as uow:
        data_file = await uow.repositories.references.create(ReferenceBuilder.file_reference_input())
        await uow.commit()
    await dataset(uow_factory, context, study_id, concept_id, reference_ids=[data_file.id])
    await set_release(uow_factory, context, ControlledModelLabel.REFERENCE, data_file.id, ReadRelease.PUBLIC)
    assert await release_of(uow_factory, ControlledModelLabel.REFERENCE, data_file.id) is ReadRelease.PUBLIC
