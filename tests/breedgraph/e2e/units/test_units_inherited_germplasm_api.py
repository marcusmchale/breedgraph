"""
Unit.inheritedGermplasm through GraphQL, on the arrivals scenario (tests/breedgraph/scenarios/arrival_scenario.py; the
view underneath is tested in tests/breedgraph/integration/views/test_inherited_germplasm_view.py): a unit with
germplasm of its own gives it as germplasm and inherits none; one without takes that of the units above it, with the
nearest unit it comes from, or none where their lineages differ or one is hidden.
"""
import pytest

from breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus

from tests.breedgraph.e2e.utils import post_as, get_verified_payload
from tests.breedgraph.scenarios.arrival_scenario import expected_germplasm

UNITS = """
query ($ids: [ID!]) {
  unitsUnits(ids: $ids) {
    status errors { message }
    result {
      id name
      germplasm { id }
      inheritedGermplasm { germplasm { id name } unit { id name } }
    }
  }
}
"""


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', ['writer', 'outsider'])
async def test_units_germplasm_own_or_inherited(client, login_token_factory, read_policy, arrivals, viewer):
    expected = expected_germplasm(arrivals, viewer)
    response = await post_as(client, login_token_factory, read_policy.user(viewer), UNITS, {
        'ids': [arrivals.units[name] for name in expected]
    })
    payload = get_verified_payload(response, 'unitsUnits')
    assert payload['status'] == GQLStatus.SUCCESS.name, payload['errors']
    found = {unit['name']: unit for unit in payload['result']}
    assert set(found) == set(expected)
    for name, value in expected.items():
        unit = found[name]
        if value is None:
            assert unit['germplasm'] is None and unit['inheritedGermplasm'] is None, name
        elif value['unit'] == name:
            assert unit['germplasm'] == {'id': str(read_policy[value['germplasm']])}, name
            assert unit['inheritedGermplasm'] is None, name
        else:
            assert unit['germplasm'] is None, name
            inherited = unit['inheritedGermplasm']
            assert inherited['germplasm']['id'] == str(read_policy[value['germplasm']]), name
            assert inherited['unit'] == {'id': str(arrivals.units[value['unit']]), 'name': value['unit']}, name
