"""
Updating a study through GraphQL: a design or licence omitted is unchanged, and null removes it.
"""
import pytest

from breedgraph.domain.model.ontology import DesignInput, VersionChange

from tests.breedgraph.e2e.utils import post_as, get_verified_payload, assert_payload_success
from tests.breedgraph.scenarios.program_builder import ProgramBuilder
from tests.breedgraph.scenarios.reference_builder import ReferenceBuilder

UPDATE = """
mutation ($study: StudyUpdate!) {
  programsUpdateStudy(study: $study) { status result errors { name message } }
}
"""
READ = """
query ($id: ID!) {
  programsStudy(id: $id) {
    status result { name design { id } licence { id } } errors { name message }
  }
}
"""


@pytest.mark.asyncio(loop_scope="session")
async def test_update_study_design_and_licence(client, login_token_factory, uow_factory, program_build_context, lorem_text_generator):
    user_id, team_id = program_build_context['user_id'], program_build_context['team_id']
    ids = await ProgramBuilder(uow_factory=uow_factory).program_trial_study(
        user_id, team_id,
        replicate_type=program_build_context['ontology_record_group_replicate'],
        batch_type=program_build_context['ontology_record_group_batch']
    )
    async with uow_factory.get_uow(user_id=user_id, write_team=team_id) as uow:
        design = await uow.ontology.create_entry(DesignInput(name=lorem_text_generator.new_text()))
        # a study links to a design of a committed version
        await uow.ontology.commit_version(version_change=VersionChange.PATCH)
        licence = await uow.repositories.references.create(ReferenceBuilder.legal_reference_input())
        await uow.commit()

    async def update(study: dict):
        payload = get_verified_payload(
            await post_as(client, login_token_factory, user_id, UPDATE, {'study': {'id': ids['study_id'], **study}}),
            'programsUpdateStudy'
        )
        assert_payload_success(payload)

    async def read() -> dict:
        payload = get_verified_payload(
            await post_as(client, login_token_factory, user_id, READ, {'id': ids['study_id']}), 'programsStudy'
        )
        assert_payload_success(payload)
        return payload['result']

    await update({'designId': design.id, 'licenceId': licence.id})
    study = await read()
    assert study['design'] == {'id': str(design.id)}
    assert study['licence'] == {'id': str(licence.id)}

    # omitted, they are unchanged
    await update({'name': 'Renamed study'})
    study = await read()
    assert study['name'] == 'Renamed study'
    assert study['design'] == {'id': str(design.id)}
    assert study['licence'] == {'id': str(licence.id)}

    # null removes each on its own
    await update({'licenceId': None})
    study = await read()
    assert study['design'] == {'id': str(design.id)}
    assert study['licence'] is None

    await update({'designId': None})
    assert (await read())['design'] is None
