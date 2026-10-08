import pytest

from breedgraph.domain.model.controls import ControlledModelLabel, ReadRelease

from tests.breedgraph.e2e.people.post_methods import _post
from tests.breedgraph.e2e.utils import get_verified_payload, assert_payload_success
from tests.breedgraph.scenarios.account_builder import AccountBuilder
from tests.breedgraph.scenarios.dataset_builder import DatasetBuilder

PERSON_REFERENCE = " id name restricted "


async def release_to_registered(uow_factory, context, label: ControlledModelLabel, entity_id: int):
    async with uow_factory.get_uow(user_id=context['user_id']) as uow:
        await uow.controls.set_controls_by_id_and_label(
            ids=[entity_id], label=label, control_teams={context['team_id']}, release=ReadRelease.REGISTERED
        )
        await uow.commit()


async def get_program_contacts(client, token, program_id: int):
    payload = get_verified_payload(await _post(
        client, token,
        f" query ( $id: ID! ) {{ programsProgram( id: $id ) {{ status, result {{ "
        f"  contacts {{ {PERSON_REFERENCE} }} trials {{ contacts {{ {PERSON_REFERENCE} }} }} "
        f" }}, errors {{ name, message }} }} }} ",
        {"id": program_id}
    ), "programsProgram")
    assert_payload_success(payload)
    return payload['result']


async def get_dataset_contributors(client, token, dataset_id: int):
    payload = get_verified_payload(await _post(
        client, token,
        f" query ( $ids: [ID!] ) {{ datasets( ids: $ids ) {{ status, result {{ "
        f"  id contributors {{ {PERSON_REFERENCE} }} "
        f" }}, errors {{ name, message }} }} }} ",
        {"ids": [dataset_id]}
    ), "datasets")
    assert_payload_success(payload)
    return payload['result'][0]['contributors']


@pytest.mark.asyncio(loop_scope="session")
async def test_contacts_and_contributors_resolve_to_persons(client, login_token_factory, uow_factory, dataset_build_context):
    context = dataset_build_context
    person_id = context['person_id']
    other_user_id = await AccountBuilder(uow_factory).account()

    async with uow_factory.get_uow(user_id=context['user_id']) as uow:
        program = await uow.repositories.programs.get(program_id=context['program_id'])
        program.contact_ids = [person_id]
        program.get_trial(context['trial_id']).contact_ids = [person_id]
        person_name = (await uow.repositories.people.get(person_id=person_id)).name
        await uow.commit()

    dataset_id = (await DatasetBuilder(uow_factory).dataset(
        context['user_id'], context['team_id'], context['concept_id'], context['study_id']
    ))['dataset_id']
    async with uow_factory.get_uow(user_id=context['user_id']) as uow:
        dataset = await uow.repositories.datasets.get(dataset_id=dataset_id)
        dataset.contributors = [person_id]
        await uow.commit()

    # Readers of the Person see it in full
    token = login_token_factory(user_id=context['user_id'])
    program = await get_program_contacts(client, token, context['program_id'])
    assert program['contacts'] == [{'id': str(person_id), 'name': person_name, 'restricted': False}]
    assert program['trials'][0]['contacts'] == program['contacts']
    assert await get_dataset_contributors(client, token, dataset_id) == program['contacts']

    # Others who can read the program and dataset, but not the Person, see the id only
    await release_to_registered(uow_factory, context, ControlledModelLabel.PROGRAM, context['program_id'])
    await release_to_registered(uow_factory, context, ControlledModelLabel.TRIAL, context['trial_id'])
    await release_to_registered(uow_factory, context, ControlledModelLabel.DATASET, dataset_id)
    other_token = login_token_factory(user_id=other_user_id)
    restricted = [{'id': str(person_id), 'name': None, 'restricted': True}]
    program = await get_program_contacts(client, other_token, context['program_id'])
    assert program['contacts'] == restricted
    assert program['trials'][0]['contacts'] == restricted
    assert await get_dataset_contributors(client, other_token, dataset_id) == restricted
