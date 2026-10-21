"""
Germplasm that units take from the units above them (Unit.inheritedGermplasm; domain.services.lineages), as the
arrivals scenario declares it for each viewer (tests/breedgraph/scenarios/arrival_scenario.py, expected_germplasm):
the nearest units with germplasm on each lineage, which must agree, and none past a hidden one.
"""
import pytest

from tests.breedgraph.scenarios.arrival_scenario import expected_germplasm


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', ['admin', 'writer', 'stranger', 'outsider'])
async def test_inherited_germplasm_as_each_viewer_sees_it(views_factory, read_policy, arrivals, viewer):
    expected = expected_germplasm(arrivals, viewer)
    async with views_factory.get_views(user_id=read_policy.user(viewer)) as views:
        inherited = await views.units.get_inherited_germplasm([arrivals.units[name] for name in expected])
    names = {unit_id: name for name, unit_id in arrivals.units.items()}
    found = {
        names[unit_id]: {'germplasm': germplasm_id, 'unit': names[source]}
        for unit_id, (germplasm_id, source) in inherited.items()
    }
    # a unit's own germplasm is not inherited: only the units whose germplasm comes from above
    wanted = {
        name: {'germplasm': read_policy[value['germplasm']], 'unit': value['unit']}
        for name, value in expected.items() if value is not None and value['unit'] != name
    }
    assert found == wanted


@pytest.mark.asyncio(loop_scope="session")
async def test_nothing_is_inherited_by_units_the_viewer_cannot_read(views_factory, read_policy, arrivals):
    async with views_factory.get_views(user_id=None) as views:
        assert await views.units.get_inherited_germplasm(arrivals.units.values()) == {}
    async with views_factory.get_views(user_id=read_policy['outsider']) as views:
        hidden = await views.units.get_inherited_germplasm([arrivals.units['Arrival Sample Hidden']])
    assert hidden == {}
