"""
An entity without controls is fixed: everyone can read it and cite it, and no one can change it, remove it or give it
controls, not even an admin of the team that made it (docs/read-access.md, rule 11). Only seeding makes such entities;
here a reference made as usual has its controls deleted, as seeding would leave it.
"""
import pytest

from breedgraph.custom_exceptions import IllegalOperationError, UnauthorisedOperationError
from breedgraph.domain.model.control_transfers import ControlledEntity
from breedgraph.domain.model.controls import ControlledModelLabel, ReadRelease
from breedgraph.domain.model.programs import StudyInput

from tests.breedgraph.scenarios.germplasm_builder import GermplasmBuilder
from tests.breedgraph.scenarios.program_builder import ProgramBuilder
from tests.breedgraph.scenarios.reference_builder import ReferenceBuilder

REFERENCE = ControlledModelLabel.REFERENCE


async def without_controls(uow_factory, label: ControlledModelLabel, entity_id: int) -> None:
    async with uow_factory.get_uow() as uow:
        await uow.tx.run(
            f"MATCH (:{label.label} {{id: $id}})<-[:CONTROLS]-(control:Control) DETACH DELETE control", id=entity_id
        )
        await uow.commit()


async def fixed_reference(uow_factory, context) -> tuple[int, str]:
    """A legal reference made by user 1 in team 1, then left without controls; its id and text"""
    reference_input = ReferenceBuilder.legal_reference_input()
    async with uow_factory.get_uow(user_id=context['user_id_1'], write_team=context['team_id_1']) as uow:
        reference = await uow.repositories.references.create(reference_input)
        await uow.commit()
    await without_controls(uow_factory, REFERENCE, reference.id)
    return reference.id, reference_input.text


@pytest.mark.asyncio(loop_scope="session")
async def test_a_fixed_reference_is_read_by_everyone(uow_factory, views_factory, control_transfer_context):
    reference_id, text = await fixed_reference(uow_factory, control_transfer_context)
    for user_id in (None, control_transfer_context['user_id_2']):
        async with views_factory.get_views(user_id=user_id) as views:
            [reference] = await views.references.get_references([reference_id])
            assert reference.text == text
            controllers = await views.controls.get_controllers(REFERENCE, [reference_id])
            assert controllers[reference_id].fixed
            assert controllers[reference_id].release is ReadRelease.PUBLIC
    async with uow_factory.get_uow(user_id=control_transfer_context['user_id_2']) as uow:
        controller = await uow.controls.get_controller(REFERENCE, reference_id)
        assert controller.fixed and controller.release is ReadRelease.PUBLIC
        await uow.controls.require_read(REFERENCE, [reference_id])


@pytest.mark.asyncio(loop_scope="session")
async def test_a_fixed_reference_can_be_a_studys_licence(uow_factory, control_transfer_context):
    reference_id, _ = await fixed_reference(uow_factory, control_transfer_context)
    async with uow_factory.get_uow(
            user_id=control_transfer_context['user_id_2'], write_team=control_transfer_context['team_id_2']
    ) as uow:
        program = await uow.repositories.programs.create(ProgramBuilder.program_input())
        program.add_trial(ProgramBuilder.trial_input())
        await uow.repositories.programs.update_seen()
        trial_id = list(program.trials.keys())[0]
        program.add_study(trial_id=trial_id, study=StudyInput(name=ProgramBuilder.program_input().name, licence_id=reference_id))
        await uow.commit()
        study = list(program.get_trial(trial_id).studies.values())[0]
    assert study.licence_id == reference_id


@pytest.mark.asyncio(loop_scope="session")
async def test_no_one_can_change_or_remove_a_fixed_reference(uow_factory, control_transfer_context, lorem_text_generator):
    reference_id, text = await fixed_reference(uow_factory, control_transfer_context)
    # user 1 administers team 1, which made it
    async with uow_factory.get_uow(
            user_id=control_transfer_context['user_id_1'], write_team=control_transfer_context['team_id_1']
    ) as uow:
        reference = await uow.repositories.references.get(reference_id=reference_id)
        reference.text = lorem_text_generator.new_text(10)
        with pytest.raises(UnauthorisedOperationError, match="has no controls"):
            await uow.commit()
    async with uow_factory.get_uow(user_id=control_transfer_context['user_id_1']) as uow:
        reference = await uow.repositories.references.get(reference_id=reference_id)
        with pytest.raises(UnauthorisedOperationError, match="has no controls"):
            await uow.repositories.references.remove(reference)
    async with uow_factory.get_uow() as uow:
        reference = await uow.repositories.references.get(reference_id=reference_id)
    assert reference.text == text


@pytest.mark.asyncio(loop_scope="session")
async def test_no_one_can_give_a_fixed_reference_controls(uow_factory, control_transfer_context):
    reference_id, _ = await fixed_reference(uow_factory, control_transfer_context)
    team_id_1 = control_transfer_context['team_id_1']
    async with uow_factory.get_uow(user_id=control_transfer_context['user_id_1']) as uow:
        with pytest.raises(IllegalOperationError, match="has no controls"):
            await uow.controls.set_controls_by_id_and_label(
                ids=[reference_id], label=REFERENCE, control_teams={team_id_1}, release=ReadRelease.PRIVATE
            )
        reference = await uow.repositories.references.get(reference_id=reference_id)
        with pytest.raises(IllegalOperationError, match="has no controls"):
            await uow.controls.set_controls(reference, control_teams={team_id_1}, release=ReadRelease.PRIVATE)
        with pytest.raises(IllegalOperationError):
            await uow.controls.offer_transfer(
                entities=[ControlledEntity(label=REFERENCE, id=reference_id)],
                from_teams={team_id_1},
                recipient_team=control_transfer_context['team_id_2']
            )
        with pytest.raises(IllegalOperationError):
            await uow.controls.renounce_controls([ControlledEntity(label=REFERENCE, id=reference_id)], {team_id_1})
    async with uow_factory.get_uow() as uow:
        assert (await uow.controls.get_controller(REFERENCE, reference_id)).fixed


@pytest.mark.asyncio(loop_scope="session")
async def test_no_one_can_change_a_fixed_germplasm_entry(uow_factory, control_transfer_context):
    """The germplasm service checks access itself, rather than through a repository"""
    germplasm_id = await GermplasmBuilder(uow_factory).germplasm(
        user_id=control_transfer_context['user_id_1'], team_id=control_transfer_context['team_id_1']
    )
    await without_controls(uow_factory, ControlledModelLabel.GERMPLASM, germplasm_id)
    async with uow_factory.get_uow(user_id=control_transfer_context['user_id_1']) as uow:
        entry = await uow.germplasm.get_entry(germplasm_id)
        entry.description = 'changed'
        with pytest.raises(UnauthorisedOperationError):
            await uow.germplasm.update_entry(entry)
        with pytest.raises(UnauthorisedOperationError):
            await uow.germplasm.delete_entry(germplasm_id)


@pytest.mark.asyncio(loop_scope="session")
async def test_new_entities_still_take_their_first_controls(uow_factory, control_transfer_context):
    """Creating notes what it creates, so a new model is not mistaken for a fixed one"""
    async with uow_factory.get_uow(
            user_id=control_transfer_context['user_id_1'], write_team=control_transfer_context['team_id_1']
    ) as uow:
        reference = await uow.repositories.references.create(ReferenceBuilder.legal_reference_input())
        program = await uow.repositories.programs.create(ProgramBuilder.program_input())
        program.add_trial(ProgramBuilder.trial_input())
        await uow.commit()
    async with uow_factory.get_uow() as uow:
        assert (await uow.controls.get_controller(REFERENCE, reference.id)).teams == {control_transfer_context['team_id_1']}
        trial_id = list(program.trials.keys())[0]
        trial_controller = await uow.controls.get_controller(ControlledModelLabel.TRIAL, trial_id)
        assert trial_controller.teams == {control_transfer_context['team_id_1']}
