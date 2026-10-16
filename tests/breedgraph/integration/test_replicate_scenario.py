"""
The replicates builder (tests/breedgraph/scenarios/replicate_scenario.py): what it declares is what the views read
back, for the outsider, who reads it only as a registered user.
"""
import pytest
import pytest_asyncio

from breedgraph.domain.model.programs import GroupingScope

from tests.breedgraph.scenarios.replicate_scenario import (
    ReplicateScenarioBuilder, DATASETS, GROUPINGS, REPLICATE, PLATE, STUDY, TREES, PLOTS, tree_name
)


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def replicates(read_policy, uow_factory):
    return await ReplicateScenarioBuilder(uow_factory, read_policy).build()


def test_units(replicates):
    assert len(replicates.units) == 2 + len(PLOTS) + len(TREES)


@pytest.mark.asyncio(loop_scope="session")
async def test_groupings(views_factory, read_policy, replicates):
    async with views_factory.get_views(user_id=read_policy['outsider']) as views:
        study = await views.programs.get_study(replicates.ids['study'])
    assert study.name == STUDY
    found = {grouping.name: grouping for grouping in study.groupings}
    assert set(found) == set(GROUPINGS)
    for name, (type_key, extent, scope) in GROUPINGS.items():
        assert (found[name].type, found[name].extent, found[name].scope) == (read_policy[type_key], extent, scope)
    pair = {replicates.datasets['same_time'], replicates.datasets['width']}
    for name in (REPLICATE, PLATE):
        assert [set(scope.dataset_ids) for scope in found[name].dataset_scopes] == [pair]
    assert all(
        not found[name].dataset_scopes for name, (_, _, scope) in GROUPINGS.items()
        if scope == GroupingScope.DATASET_SCOPED and name not in (REPLICATE, PLATE)
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_datasets(views_factory, read_policy, replicates):
    async with views_factory.get_views(user_id=read_policy['outsider']) as views:
        summaries = {summary.id: summary for summary in await views.datasets.get_dataset_summaries(replicates.ids['study'])}
        assert set(summaries) == set(replicates.datasets.values())
        for key, (concept_key, records) in DATASETS.items():
            summary = summaries[replicates.datasets[key]]
            assert summary.concept_id == read_policy[concept_key]
            assert summary.record_count == len(records)

        stored = await views.datasets.get_records(replicates.datasets['same_time'])
    names = {unit_id: name for name, unit_id in replicates.units.items()}
    by_id = {grouping_id: name for name, grouping_id in replicates.groupings.items()}
    expected = sorted(
        (record.unit, record.value, tuple(sorted(record.groups))) for record in DATASETS['same_time'][1]
    )
    found = sorted(
        (names[record['unit']], record['value'], tuple(sorted((by_id[g['id']], g['code']) for g in record['groups'])))
        for record in stored
    )
    assert found == expected
    assert sum(1 for record in stored if names[record['unit']] == tree_name('A', 6)) == 2
