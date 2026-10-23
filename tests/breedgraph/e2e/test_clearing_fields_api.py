"""
Update mutations pass on what they are given: a field left out is unchanged, and null clears an optional one
(README, Updates)
"""
import pytest

from breedgraph.domain.model.references import ExternalDataInput, DataFormat

from tests.breedgraph.e2e.utils import post_as, get_verified_payload, assert_payload_success
from tests.breedgraph.scenarios.program_builder import ProgramBuilder
from tests.breedgraph.scenarios.unit_graph_builder import UnitGraphBuilder

UPDATE_TRIAL = """
mutation ($trial: TrialUpdate!) { programsUpdateTrial(trial: $trial) { status result errors { name message } } }
"""
UPDATE_UNIT = """
mutation ($unit: UnitUpdate!) { unitsUpdateUnit(unit: $unit) { status result errors { name message } } }
"""
UPDATE_EXTERNAL_DATA = """
mutation ($reference: ExternalDataReferenceUpdate!) {
  referencesUpdateExternalData(reference: $reference) { status result errors { name message } }
}
"""


async def mutate(client, login_token_factory, user_id, query, name, variables):
    response = await post_as(client, login_token_factory, user_id, query, variables)
    assert_payload_success(get_verified_payload(response, name))


@pytest.mark.asyncio(loop_scope="session")
async def test_fields_left_out_stay_and_null_clears(client, login_token_factory, uow_factory, program_build_context):
    user_id, team_id = program_build_context['user_id'], program_build_context['team_id']
    ids = await ProgramBuilder(uow_factory=uow_factory).program_trial_study(
        user_id, team_id,
        replicate_type=program_build_context['ontology_record_group_replicate'],
        batch_type=program_build_context['ontology_record_group_batch']
    )
    unit_id = await UnitGraphBuilder(uow_factory=uow_factory).unit(user_id=user_id, team_id=team_id)
    async with uow_factory.get_uow(user_id=user_id, write_team=team_id) as uow:
        reference = await uow.repositories.references.create(ExternalDataInput(
            url="https://example.org/table", format=DataFormat.CSV, description="A table", external_id="T1",
            schema={"type": "object"}
        ))
        await uow.commit()

    async def post(query, name, variables):
        await mutate(client, login_token_factory, user_id, query, name, variables)

    trial = {'id': ids['trial_id']}
    await post(UPDATE_TRIAL, 'programsUpdateTrial', {'trial': {**trial, 'fullname': "Full", 'description': "About"}})
    await post(UPDATE_TRIAL, 'programsUpdateTrial', {'trial': {**trial, 'description': None}})
    await post(UPDATE_UNIT, 'unitsUpdateUnit', {'unit': {'id': unit_id, 'name': "Tree", 'description': "Tall"}})
    await post(UPDATE_UNIT, 'unitsUpdateUnit', {'unit': {'id': unit_id, 'description': None}})
    # the schema left out is unchanged; the external id given as null is cleared
    await post(UPDATE_EXTERNAL_DATA, 'referencesUpdateExternalData', {'reference': {
        'id': reference.id, 'url': "https://example.org/table", 'format': 'CSV', 'externalId': None
    }})

    async with uow_factory.get_uow(user_id=user_id) as uow:
        program = await uow.repositories.programs.get(trial_id=ids['trial_id'])
        stored_trial = program.trials[ids['trial_id']]
        assert (stored_trial.fullname, stored_trial.description) == ("Full", None)
        unit = (await uow.repositories.unit_graphs.get(unit_id=unit_id)).get_unit(unit_id)
        assert (unit.name, unit.description) == ("Tree", None)
        stored_reference = await uow.repositories.references.get(reference_id=reference.id)
        assert (stored_reference.description, stored_reference.external_id, stored_reference.schema) == (
            "A table", None, {"type": "object"}
        )
