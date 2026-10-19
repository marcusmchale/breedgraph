"""
The dataset queries under the read policy, through GraphQL, on the read-policy scenario
(see tests/breedgraph/integration/views/test_datasets_read_policy.py for the view underneath).
They answer anonymous requests. A hidden dataset asked for by id is a placeholder with no records, counts, unit ids
or dimensions, and datasets the viewer cannot read contribute nothing to datasetsUnits or datasetsUnitsBySubject.
"""
import pytest

from breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus

from tests.breedgraph.e2e.utils import post_as, get_verified_payload
from tests.breedgraph.scenarios.read_policy_scenario import VIEWERS, DATASETS, UNIT_PARENTS

REDACTED = 'REDACTED'

DATASET_FIELDS = (
    "id studyId concept { id } recordCount unitIds dimensions { recordCount unitCount } "
    "contributions { person { id } roles { name } } references { id } "
    "records { value unit { id name } references { id } }"
)


async def query(client, login_token_factory, read_policy, viewer: str, operation: str, text: str, variables=None):
    response = await post_as(client, login_token_factory, read_policy.user(viewer), text, variables)
    payload = get_verified_payload(response, operation)
    # an empty list is a valid result here, so not assert_payload_success
    assert payload['status'] == GQLStatus.SUCCESS.name, payload['errors']
    assert payload['errors'] is None
    return payload['result']


def as_ids(entities) -> set[int]:
    return {int(entity['id']) for entity in entities or []}


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_datasets_by_id(client, login_token_factory, read_policy, viewer):
    result = await query(
        client, login_token_factory, read_policy, viewer, 'datasets',
        f"query ($ids: [ID!]) {{ datasets(ids: $ids) {{ status result {{ {DATASET_FIELDS} }} errors {{ name message }} }} }}",
        {'ids': [read_policy[name] for name in DATASETS]}
    )
    datasets = {int(dataset['id']): dataset for dataset in result}
    assert set(datasets) == {read_policy[name] for name in DATASETS}
    for name, expected in DATASETS.items():
        dataset = datasets[read_policy[name]]
        if read_policy.readable(viewer, name):
            assert int(dataset['studyId']) == read_policy[expected['study']]
            assert int(dataset['concept']['id']) == read_policy['ontology_variable_height']
            assert dataset['recordCount'] == len(expected['records'])
            assert {int(unit_id) for unit_id in dataset['unitIds']} == {read_policy[unit] for unit, _, _ in expected['records']}
            assert dataset['dimensions']['recordCount'] == len(expected['records'])
            # anonymous users get no contributors, as they see no Persons (docs/person.md §3)
            assert {
                (int(contribution['person']['id']), tuple(role['name'] for role in contribution['roles']))
                for contribution in dataset['contributions']
            } == (set() if viewer == 'anonymous' else {
                (read_policy[person], tuple(roles)) for person, roles in expected['contributions']
            })
            assert as_ids(dataset['references']) == {read_policy[reference] for reference in expected['references']}
            # each record's unit is named where the viewer can read it, a placeholder otherwise (rule 2)
            records = {record['value']: record for record in dataset['records']}
            assert set(records) == {value for _, value, _ in expected['records']}
            for unit, value, references in expected['records']:
                record = records[value]
                assert int(record['unit']['id']) == read_policy[unit]
                assert (record['unit']['name'] != REDACTED) == read_policy.readable(viewer, unit), f"{viewer}: {unit}"
                assert as_ids(record['references']) == {read_policy[reference] for reference in references}
        else:
            assert dataset['studyId'] is None
            assert dataset['concept'] is None
            assert dataset['recordCount'] == 0
            assert dataset['unitIds'] == []
            assert dataset['dimensions'] is None
            assert dataset['records'] == []
            assert not dataset['contributions']
            assert not dataset['references']


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_dataset_searches_leave_hidden_out(client, login_token_factory, read_policy, viewer):
    result = await query(
        client, login_token_factory, read_policy, viewer, 'datasets',
        "query ($studyIds: [ID!]) { datasets(studyIds: $studyIds) { status result { id } errors { name message } } }",
        {'studyIds': [read_policy['study_public'], read_policy['study_registered']]}
    )
    assert as_ids(result) == {read_policy[name] for name in DATASETS if read_policy.readable(viewer, name)}


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_dataset_summaries(client, login_token_factory, read_policy, viewer):
    result = await query(
        client, login_token_factory, read_policy, viewer, 'datasetsSummaries',
        "query ($studyId: ID!) { datasetsSummaries(studyId: $studyId) { "
        "  status result { id record_count unit_count subjects { id } unitRoots { id name } locations { id name } } "
        "  errors { name message } } }",
        {'studyId': read_policy['study_public']}
    )
    expected = [name for name in ('dataset_public', 'dataset_private') if read_policy.readable(viewer, name)]
    summaries = {int(summary['id']): summary for summary in result}
    assert set(summaries) == {read_policy[name] for name in expected}
    for name in expected:
        summary = summaries[read_policy[name]]
        assert summary['record_count'] == len(DATASETS[name]['records'])
        # the unit graph root is linked even though the viewer may not read it, as a placeholder
        for unit_graph in summary['unitRoots']:
            assert int(unit_graph['id']) == read_policy['field_unit']
            assert (unit_graph['name'] != REDACTED) == read_policy.readable(viewer, 'field_unit')
        # tree_public is at the private state
        for location in summary['locations']:
            assert int(location['id']) == read_policy['state']
            assert (location['name'] != REDACTED) == read_policy.readable(viewer, 'state')


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_datasets_units(client, login_token_factory, read_policy, viewer):
    """Asked with every dataset, the tree is that of the readable ones only; with hidden ones only, it is empty"""
    text = (
        "query ($datasetIds: [ID!]!, $parentIds: [ID!]) { datasetsUnits(datasetIds: $datasetIds, parentIds: $parentIds) { "
        "  status result { unit { id name } unitCount recordCount hasChildren } errors { name message } } }"
    )
    readable = [name for name in DATASETS if read_policy.readable(viewer, name)]
    hidden = [name for name in DATASETS if name not in readable]
    names = {read_policy[unit]: unit for unit in UNIT_PARENTS}

    pending = [None]
    while pending:
        parent = pending.pop()
        result = await query(
            client, login_token_factory, read_policy, viewer, 'datasetsUnits', text,
            {'datasetIds': [read_policy[name] for name in DATASETS], 'parentIds': [read_policy[parent]] if parent else None}
        )
        level = {names[int(node['unit']['id'])]: node for node in result}
        expected = read_policy.recorded_unit_level(viewer, readable, parent)
        assert {unit: (node['unitCount'], node['recordCount'], node['hasChildren']) for unit, node in level.items()} == \
            expected, f"{viewer}: below {parent}"
        for unit, node in level.items():
            assert (node['unit']['name'] != REDACTED) == read_policy.readable(viewer, unit)
        pending.extend(unit for unit, node in level.items() if node['hasChildren'])

    if hidden:
        assert await query(
            client, login_token_factory, read_policy, viewer, 'datasetsUnits', text,
            {'datasetIds': [read_policy[name] for name in hidden], 'parentIds': None}
        ) == []


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_datasets_units_by_subject(client, login_token_factory, read_policy, viewer):
    text = (
        "query ($datasetIds: [ID!]!) { datasetsUnitsBySubject(datasetIds: $datasetIds) { "
        "  status result { subject { id } units { id name } } errors { name message } } }"
    )
    readable = [name for name in DATASETS if read_policy.readable(viewer, name)]
    hidden = [name for name in DATASETS if name not in readable]
    result = await query(
        client, login_token_factory, read_policy, viewer, 'datasetsUnitsBySubject', text,
        {'datasetIds': [read_policy[name] for name in DATASETS]}
    )
    recorded = {unit for name in readable for unit, _, _ in DATASETS[name]['records']}
    found = {int(unit['id']): (group['subject'], unit['name']) for group in result for unit in group['units']}
    assert set(found) == {read_policy[unit] for unit in recorded}
    for unit in recorded:
        subject, unit_name = found[read_policy[unit]]
        assert (subject is None) == (unit_name == REDACTED) == (not read_policy.readable(viewer, unit))

    if hidden:
        assert await query(
            client, login_token_factory, read_policy, viewer, 'datasetsUnitsBySubject', text,
            {'datasetIds': [read_policy[name] for name in hidden]}
        ) == []
