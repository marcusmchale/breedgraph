"""
The germplasm queries under the read policy, through GraphQL, on the read-policy scenario
(see tests/breedgraph/integration/views/test_germplasm_view.py for the view underneath).
They answer anonymous requests, and a relationship's source and sink resolve to the view's entries: a hidden crop
named as a source resolves to its placeholder. The unit an entry came from resolves through the units view, a
placeholder where hidden.
"""
import pytest

from breedgraph.adapters.neo4j.views.units import Neo4jUnitsView
from breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus

from tests.breedgraph.e2e.utils import post_as, get_verified_payload
from tests.breedgraph.scenarios.read_policy_scenario import VIEWERS, GERMPLASM

REDACTED = 'REDACTED'

ENTRY_FIELDS = (
    "id name description "
    "sources { sourceType source { id name } sink { id } } "
    "sinks { sourceType sink { id name } source { id } }"
)


async def query(client, login_token_factory, read_policy, viewer: str, operation: str, text: str, variables=None):
    response = await post_as(client, login_token_factory, read_policy.user(viewer), text, variables)
    payload = get_verified_payload(response, operation)
    # an empty list is a valid result here, so not assert_payload_success
    assert payload['status'] == GQLStatus.SUCCESS.name, payload['errors']
    assert payload['errors'] is None
    return payload['result']


def assert_entry(read_policy, viewer: str, name: str, entry: dict):
    expected = read_policy.germplasm_entry(viewer, name)
    names = {read_policy[other]: other for other in GERMPLASM}
    assert int(entry['id']) == read_policy[name]
    assert (entry['name'] != REDACTED) == expected.readable, f"{viewer}: {name}"
    sources = {names[int(link['source']['id'])]: link for link in entry['sources'] or []}
    sinks = {names[int(link['sink']['id'])]: link for link in entry['sinks'] or []}
    assert {other: link['sourceType'] for other, link in sources.items()} == expected.sources, f"{viewer}: sources of {name}"
    assert {other: link['sourceType'] for other, link in sinks.items()} == expected.sinks, f"{viewer}: sinks of {name}"
    for other, link in sources.items():
        assert int(link['sink']['id']) == read_policy[name]
        # a source may be a hidden crop, which resolves to its placeholder
        assert (link['source']['name'] != REDACTED) == read_policy.readable(viewer, other)
    for other, link in sinks.items():
        assert int(link['source']['id']) == read_policy[name]
        assert link['sink']['name'] != REDACTED


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_entries_by_id(client, login_token_factory, read_policy, viewer):
    result = await query(
        client, login_token_factory, read_policy, viewer, 'germplasmEntries',
        f"query ($ids: [ID!]) {{ germplasmEntries(ids: $ids) {{ status result {{ {ENTRY_FIELDS} }} errors {{ name message }} }} }}",
        {'ids': [read_policy[name] for name in GERMPLASM]}
    )
    entries = {int(entry['id']): entry for entry in result}
    assert set(entries) == {read_policy[name] for name in GERMPLASM}
    for name in GERMPLASM:
        assert_entry(read_policy, viewer, name, entries[read_policy[name]])


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_all_entries_leave_hidden_out(client, login_token_factory, read_policy, viewer):
    result = await query(
        client, login_token_factory, read_policy, viewer, 'germplasmEntries',
        f"query {{ germplasmEntries {{ status result {{ {ENTRY_FIELDS} }} errors {{ name message }} }} }}"
    )
    entries = {int(entry['id']): entry for entry in result}
    expected = [name for name in GERMPLASM if read_policy.readable(viewer, name)]
    assert set(entries) == {read_policy[name] for name in expected}
    for name in expected:
        assert_entry(read_policy, viewer, name, entries[read_policy[name]])


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_crops(client, login_token_factory, read_policy, viewer):
    result = await query(
        client, login_token_factory, read_policy, viewer, 'germplasmCrops',
        f"query {{ germplasmCrops {{ status result {{ {ENTRY_FIELDS} }} errors {{ name message }} }} }}"
    )
    crops = {int(entry['id']): entry for entry in result}
    expected = read_policy.shown_crops(viewer)
    assert set(crops) == {read_policy[name] for name in expected}
    for name in expected:
        assert_entry(read_policy, viewer, name, crops[read_policy[name]])


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize('viewer', VIEWERS)
async def test_entries_name_their_units(client, login_token_factory, read_policy, germplasm_units, viewer):
    result = await query(
        client, login_token_factory, read_policy, viewer, 'germplasmEntries',
        "query ($ids: [ID!]) { germplasmEntries(ids: $ids) { status result { id name unit { id name } } "
        "errors { name message } } }",
        {'ids': [read_policy[name] for name in germplasm_units]}
    )
    entries = {int(entry['id']): entry for entry in result}
    for name, unit in germplasm_units.items():
        entry = entries[read_policy[name]]
        if read_policy.readable(viewer, name):
            assert int(entry['unit']['id']) == read_policy[unit], f"{viewer}: {name}"
            assert (entry['unit']['name'] != REDACTED) == read_policy.readable(viewer, unit), f"{viewer}: {unit}"
        else:
            assert entry['unit'] is None, f"{viewer}: {name}"


@pytest.mark.asyncio(loop_scope="session")
async def test_the_units_of_a_list_are_read_at_once(client, login_token_factory, read_policy, germplasm_units, monkeypatch):
    reads = []
    get_units = Neo4jUnitsView._get_units

    async def counted(self, unit_ids):
        reads.append(sorted(unit_ids))
        return await get_units(self, unit_ids)

    monkeypatch.setattr(Neo4jUnitsView, '_get_units', counted)
    await query(
        client, login_token_factory, read_policy, 'writer', 'germplasmEntries',
        "query ($ids: [ID!]) { germplasmEntries(ids: $ids) { status result { id unit { id } } errors { name message } } }",
        {'ids': [read_policy[name] for name in germplasm_units]}
    )
    assert reads == [sorted(read_policy[unit] for unit in germplasm_units.values())]
