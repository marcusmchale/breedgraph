"""
Record groupings of a study through GraphQL: each sets its own extent, beside its scope,
whatever the default extent of its type.
"""
import pytest

from tests.breedgraph.e2e.utils import post_as, get_verified_payload, assert_payload_success
from tests.breedgraph.scenarios.program_builder import ProgramBuilder

CREATE = """
mutation ($grouping: GroupingInput!) {
  programsCreateGrouping(grouping: $grouping) { status result errors { name message } }
}
"""
UPDATE = """
mutation ($grouping: GroupingUpdate!) {
  programsUpdateGrouping(grouping: $grouping) { status result errors { name message } }
}
"""
READ = """
query ($id: ID!) {
  programsStudy(id: $id) {
    status result { groupings { id name scope extent type { id defaultExtent } } } errors { name message }
  }
}
"""


@pytest.mark.asyncio(loop_scope="session")
async def test_create_and_update_grouping_extent(client, login_token_factory, uow_factory, program_build_context):
    user_id = program_build_context['user_id']
    plate_type = program_build_context['ontology_record_group_plate']  # a type without a default extent
    ids = await ProgramBuilder(uow_factory=uow_factory).program_trial_study(
        user_id, program_build_context['team_id'],
        replicate_type=program_build_context['ontology_record_group_replicate'],
        batch_type=program_build_context['ontology_record_group_batch']
    )

    async def post(query: str, variables: dict):
        return await post_as(client, login_token_factory, user_id, query, variables)

    async def read_grouping(name: str) -> dict:
        payload = get_verified_payload(await post(READ, {'id': ids['study_id']}), 'programsStudy')
        assert_payload_success(payload)
        return next(grouping for grouping in payload['result']['groupings'] if grouping['name'] == name)

    grouping = {'studyId': ids['study_id'], 'typeId': plate_type, 'name': 'Plate', 'scope': 'STUDY_WIDE'}
    # the extent is required
    assert (await post(CREATE, {'grouping': grouping})).json().get('errors')

    assert_payload_success(get_verified_payload(
        await post(CREATE, {'grouping': {**grouping, 'extent': 'WITHIN_GRAPH'}}), 'programsCreateGrouping'
    ))
    plate = await read_grouping('Plate')
    assert plate['extent'] == 'WITHIN_GRAPH'
    assert plate['type'] == {'id': str(plate_type), 'defaultExtent': None}
    # the builder's groupings have their own extents
    assert (await read_grouping('Dataset Scoped Replicate'))['extent'] == 'WITHIN_UNIT'

    update = {'id': plate['id'], 'typeId': plate_type, 'name': 'Plate', 'scope': 'STUDY_WIDE'}
    assert_payload_success(get_verified_payload(
        await post(UPDATE, {'grouping': {**update, 'extent': 'SHARED'}}), 'programsUpdateGrouping'
    ))
    assert (await read_grouping('Plate'))['extent'] == 'SHARED'

    # omitted on update, it is unchanged
    assert_payload_success(get_verified_payload(
        await post(UPDATE, {'grouping': {**update, 'name': 'Plates'}}), 'programsUpdateGrouping'
    ))
    assert (await read_grouping('Plates'))['extent'] == 'SHARED'
