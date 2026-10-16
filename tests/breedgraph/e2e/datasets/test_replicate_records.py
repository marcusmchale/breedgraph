"""
The replicates study's records through GraphQL, as curation reads them: each record's codes, and the codes of each
grouping in a dataset's dimensions, are those the scenario declares (tests/breedgraph/scenarios/replicate_scenario.py).
"""
import pytest

from tests.breedgraph.e2e.datasets.test_datasets_read_api import query
from tests.breedgraph.scenarios.replicate_scenario import DATASETS


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('dataset', DATASETS)
async def test_codes(dataset, client, login_token_factory, read_policy, replicates):
    result = await query(
        client, login_token_factory, read_policy, 'writer', 'datasets',
        "query ($ids: [ID!]) { datasets(ids: $ids) { status result { "
        " records { value start unit { id } groups { id code } } "
        " dimensions { groups { groupingId codes } } "
        "} errors { name message } } }",
        {'ids': [replicates.datasets[dataset]]}
    )
    found, = result
    units = {unit_id: name for name, unit_id in replicates.units.items()}
    groupings = {grouping_id: name for name, grouping_id in replicates.groupings.items()}
    records = DATASETS[dataset][1]

    assert sorted(
        (units[int(r['unit']['id'])], r['value'], tuple(sorted((groupings[int(g['id'])], g['code']) for g in r['groups'])))
        for r in found['records']
    ) == sorted((r.unit, r.value, tuple(sorted(r.groups))) for r in records)

    codes = {}
    for record in records:
        for name, code in record.groups:
            codes.setdefault(name, set()).add(code)
    assert {
        groupings[int(g['groupingId'])]: g['codes'] for g in found['dimensions']['groups']
    } == {name: sorted(found_codes) for name, found_codes in codes.items()}
