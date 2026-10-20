"""
Updating a unit through GraphQL: a subject or germplasm omitted is unchanged, and null removes it.
"""
import pytest

from tests.breedgraph.e2e.utils import post_as, get_verified_payload, assert_payload_success
from tests.breedgraph.scenarios.germplasm_builder import GermplasmBuilder
from tests.breedgraph.scenarios.unit_graph_builder import UnitGraphBuilder

UPDATE = """
mutation ($unit: UnitUpdate!) {
  unitsUpdateUnit(unit: $unit) { status result errors { name message } }
}
"""
READ = """
query ($ids: [ID!]) {
  unitsUnits(ids: $ids) { status result { name subject { id } germplasm { id } } errors { name message } }
}
"""


@pytest.mark.asyncio(loop_scope="session")
async def test_update_unit_subject_and_germplasm(client, login_token_factory, uow_factory, unit_graph_build_context):
    user_id, team_id = unit_graph_build_context['user_id'], unit_graph_build_context['team_id']
    subject_id = unit_graph_build_context['ontology_subject_tree']
    germplasm_id = await GermplasmBuilder(uow_factory=uow_factory).germplasm(user_id=user_id, team_id=team_id)
    unit_id = await UnitGraphBuilder(uow_factory=uow_factory).unit(user_id=user_id, team_id=team_id)

    async def update(unit: dict):
        payload = get_verified_payload(
            await post_as(client, login_token_factory, user_id, UPDATE, {'unit': {'id': unit_id, **unit}}),
            'unitsUpdateUnit'
        )
        assert_payload_success(payload)

    async def read() -> dict:
        payload = get_verified_payload(
            await post_as(client, login_token_factory, user_id, READ, {'ids': [unit_id]}), 'unitsUnits'
        )
        assert_payload_success(payload)
        return payload['result'][0]

    await update({'subjectId': subject_id, 'germplasmId': germplasm_id})
    unit = await read()
    assert unit['subject'] == {'id': str(subject_id)}
    assert unit['germplasm'] == {'id': str(germplasm_id)}

    # omitted, they are unchanged
    await update({'name': 'Renamed unit'})
    unit = await read()
    assert unit['name'] == 'Renamed unit'
    assert unit['subject'] == {'id': str(subject_id)}
    assert unit['germplasm'] == {'id': str(germplasm_id)}

    # null removes each on its own
    await update({'germplasmId': None})
    unit = await read()
    assert unit['subject'] == {'id': str(subject_id)}
    assert unit['germplasm'] is None

    await update({'subjectId': None})
    assert (await read())['subject'] is None
