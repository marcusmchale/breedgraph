"""
The scale builder (tests/breedgraph/scenarios/scale_scenario.py) at a small size: what it reports is what the views
read back, for the admin, who reads the child team's private data, and for the outsider, who reads none of it.
"""
import pytest
import pytest_asyncio

from tests.breedgraph.scenarios.scale_scenario import ScaleScenarioBuilder, ScaleParameters, field_key, study_key

PARAMETERS = ScaleParameters(fields=2, trees_per_field=3, leaves_per_tree=2, datasets_per_concept=2, records_per_unit=3)


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def scale(read_policy, uow_factory):
    return await ScaleScenarioBuilder(uow_factory, read_policy, PARAMETERS).build()


def test_counts(scale):
    p = PARAMETERS
    assert scale.unit_count == p.fields * (1 + p.trees_per_field * (1 + p.leaves_per_tree))
    large = p.datasets_per_concept * p.trees_per_field * p.records_per_unit
    assert scale.record_count == large + (p.fields - 1) * p.trees_per_field


@pytest.mark.asyncio(loop_scope="session")
async def test_admin_reads_it_all(views_factory, read_policy, scale):
    p = PARAMETERS
    async with views_factory.get_views(user_id=read_policy['admin']) as views:
        locations = await views.location_trees.get_locations([scale.ids[field_key(n)] for n in range(1, p.fields + 1)])
        assert {location.name for location in locations.values()} == {scale.names[field_key(n)] for n in range(1, p.fields + 1)}

        roots = await views.units.get_unit_graph_roots([scale.ids[field_key(1)]])
        assert [root.id for root in roots] == [scale.ids['scale_field_unit_01']]
        by_subject = await views.units.get_descendants_by_subject([roots[0].id])
        assert sorted(len(units) for units in by_subject.values()) == sorted([p.trees_per_field, p.trees_per_field * p.leaves_per_tree])

        study = await views.programs.get_study(scale.ids[study_key(1)])
        assert study.name == scale.names[study_key(1)]
        summaries = await views.datasets.get_dataset_summaries(scale.ids[study_key(1)])
        assert sorted(summary.id for summary in summaries) == sorted(scale.dataset_ids[study_key(1)])
        assert all(summary.record_count == p.trees_per_field * p.records_per_unit for summary in summaries)
        assert all(summary.unit_count == p.trees_per_field for summary in summaries)


@pytest.mark.asyncio(loop_scope="session")
async def test_outsider_reads_none_of_it(views_factory, read_policy, scale):
    async with views_factory.get_views(user_id=read_policy['outsider']) as views:
        assert await views.datasets.get_datasets(study_ids=[scale.ids[study_key(1)]]) == []
        assert await views.units.get_unit_graph_roots([scale.ids[field_key(1)]]) == []
        study = await views.programs.get_study(scale.ids[study_key(1)])
        assert study.name == 'REDACTED'
