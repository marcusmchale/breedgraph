"""
Controllers under the read policy (docs/read-access.md, rule 8), for every entity of the read-policy scenario.

The controller of an entity the viewer can read is returned in full: its current controls, when and by whom they were
set, and the writes to it. For an entity they cannot read it is a placeholder: the controlling teams and releases
alone, so they see whom to ask for access, without times, users or writes.
"""
from collections import defaultdict

import pytest

from breedgraph.domain.model.controls import ReadRelease

from tests.breedgraph.scenarios.read_policy_scenario import VIEWERS, ENTITY_LABELS

WRITERS = {'root': 'admin', 'child': 'writer', 'other': 'stranger'}


def test_every_entity_has_a_label(read_policy):
    assert set(ENTITY_LABELS) == set(read_policy.controls)


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_controllers(views_factory, read_policy, viewer):
    by_label = defaultdict(list)
    for name, label in ENTITY_LABELS.items():
        by_label[label].append(name)

    async with views_factory.get_views(user_id=read_policy.user(viewer)) as views:
        for label, names in by_label.items():
            controllers = await views.controls.get_controllers(label, [read_policy[name] for name in names])
            assert set(controllers) == {read_policy[name] for name in names}
            for name in names:
                controller = controllers[read_policy[name]]
                team, release = read_policy.controls[name]
                # the controls are shown either way: whom to ask for access
                assert {team_id: control.release for team_id, control in controller.controls.items()} == \
                    {read_policy[team]: ReadRelease(release)}, f"{viewer}: controls of {name}"
                control = controller.controls[read_policy[team]]
                if read_policy.readable(viewer, name):
                    assert control.time is not None
                    assert control.user_id == read_policy[WRITERS[team]]
                    assert controller.writes, f"{viewer} should see the writes to {name}"
                    assert controller.writes[0].user == read_policy[WRITERS[team]]
                    assert controller.writes == sorted(controller.writes, key=lambda write: write.time)
                else:
                    assert control.time is None, f"{viewer}: time of the control of {name}"
                    assert control.user_id is None
                    assert controller.writes == [], f"{viewer} should not see the writes to {name}"


@pytest.mark.asyncio(loop_scope="session")
async def test_missing_entities_are_left_out(views_factory, read_policy):
    missing = max(read_policy.ids.values()) + 1000
    async with views_factory.get_views(user_id=read_policy.user('admin')) as views:
        controllers = await views.controls.get_controllers(ENTITY_LABELS['country'], [missing, read_policy['country']])
    assert set(controllers) == {read_policy['country']}
