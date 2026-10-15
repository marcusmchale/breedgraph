"""
The read-policy scenario builds, and its expectations (ReadPolicyScenario.readable and tree_member) say what
docs/read-access.md says for a few cases worked out by hand. The domain tests rely on them.
"""
import pytest

from tests.breedgraph.scenarios.read_policy_scenario import TreeMember, LOCATION_PARENTS


@pytest.mark.asyncio(loop_scope="session")
async def test_scenario_controls(read_policy):
    assert read_policy.readable('admin', 'state')
    assert not read_policy.readable('admin', 'centre')
    assert read_policy.readable('outsider', 'lab')
    assert not read_policy.readable('outsider', 'state')
    assert not read_policy.readable('anonymous', 'field_registered')
    assert read_policy.readable('anonymous', 'field')
    assert read_policy.readable('stranger', 'centre')


@pytest.mark.asyncio(loop_scope="session")
async def test_tree_member(read_policy):
    member = lambda viewer, name: read_policy.tree_member(viewer, LOCATION_PARENTS, name)
    # the outsider skips state and centre
    assert member('outsider', 'country') == TreeMember(True, 'country', None, {'field', 'field_registered'})
    assert member('outsider', 'field') == TreeMember(True, 'country', 'country', {'lab'})
    assert member('outsider', 'lab') == TreeMember(True, 'country', 'field', set())
    assert member('outsider', 'state') == TreeMember(False, 'country', None, set())
    # a hidden root is kept, with its readable descendants
    assert member('anonymous', 'country_private') == TreeMember(False, 'country_private', None, {'state_public'})
    assert member('anonymous', 'state_public') == TreeMember(True, 'country_private', 'country_private', set())
    # the admin skips only the stranger's centre
    assert member('admin', 'field') == TreeMember(True, 'country', 'state', {'lab'})
    assert read_policy.shown_roots('anonymous', LOCATION_PARENTS) == {'country', 'country_private'}
