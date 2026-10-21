"""
Updating a germplasm entry through GraphQL: an origin omitted is unchanged and null removes it, and references
omitted are unchanged. The unit it came from, given when it is created, is changed in the same way as the origin.
"""
import pytest

from tests.breedgraph.e2e.utils import post_as, get_verified_payload, assert_payload_success
from tests.breedgraph.scenarios.germplasm_builder import GermplasmBuilder
from tests.breedgraph.scenarios.reference_builder import ReferenceBuilder
from tests.breedgraph.scenarios.unit_graph_builder import UnitGraphBuilder

UPDATE = """
mutation ($entry: GermplasmUpdate!) {
  germplasmUpdateEntry(entry: $entry) { status result errors { name message } }
}
"""
READ = """
query ($ids: [ID!]) {
  germplasmEntries(ids: $ids) { status result { name origin { id } references { id } } errors { name message } }
}
"""


@pytest.mark.asyncio(loop_scope="session")
async def test_update_germplasm_origin(client, login_token_factory, uow_factory, unit_graph_build_context):
    user_id, team_id = unit_graph_build_context['user_id'], unit_graph_build_context['team_id']
    location_id = unit_graph_build_context['location_id']
    entry_id = await GermplasmBuilder(uow_factory=uow_factory).germplasm(user_id=user_id, team_id=team_id)
    async with uow_factory.get_uow(user_id=user_id, write_team=team_id) as uow:
        reference = await uow.repositories.references.create(ReferenceBuilder.legal_reference_input())
        await uow.commit()

    async def update(entry: dict):
        payload = get_verified_payload(
            await post_as(client, login_token_factory, user_id, UPDATE, {'entry': {'id': entry_id, **entry}}),
            'germplasmUpdateEntry'
        )
        assert_payload_success(payload)

    async def read() -> dict:
        payload = get_verified_payload(
            await post_as(client, login_token_factory, user_id, READ, {'ids': [entry_id]}), 'germplasmEntries'
        )
        assert_payload_success(payload)
        return payload['result'][0]

    await update({'originId': location_id, 'referenceIds': [reference.id]})
    entry = await read()
    assert entry['origin'] == {'id': str(location_id)}
    assert entry['references'] == [{'id': str(reference.id)}]

    # omitted, they are unchanged
    await update({'name': 'Renamed entry'})
    entry = await read()
    assert entry['name'] == 'Renamed entry'
    assert entry['origin'] == {'id': str(location_id)}
    assert entry['references'] == [{'id': str(reference.id)}]

    # null removes the origin
    await update({'originId': None})
    entry = await read()
    assert entry['origin'] is None
    assert entry['references'] == [{'id': str(reference.id)}]


CREATE = """
mutation ($entry: GermplasmInput!, $teamId: ID!) {
  germplasmCreateEntry(entry: $entry, controlTeamId: $teamId) { status result errors { name message } }
}
"""
READ_UNIT = """
query ($ids: [ID!]) {
  germplasmEntries(ids: $ids) { status result { name unit { id name } } errors { name message } }
}
"""


@pytest.mark.asyncio(loop_scope="session")
async def test_create_and_update_germplasm_unit(client, login_token_factory, uow_factory, unit_graph_build_context):
    user_id, team_id = unit_graph_build_context['user_id'], unit_graph_build_context['team_id']
    unit_builder = UnitGraphBuilder(uow_factory=uow_factory)
    unit_id = await unit_builder.unit(user_id=user_id, team_id=team_id)
    other_unit_id = await unit_builder.unit(user_id=user_id, team_id=team_id)
    name = GermplasmBuilder.germplasm_input().name

    async def post(text: str, variables: dict, operation: str):
        payload = get_verified_payload(await post_as(client, login_token_factory, user_id, text, variables), operation)
        assert_payload_success(payload)
        return payload['result']

    await post(CREATE, {'entry': {'name': name, 'unitId': unit_id}, 'teamId': team_id}, 'germplasmCreateEntry')
    async with uow_factory.get_uow(user_id=user_id) as uow:
        (entry_id,) = [entry.id async for entry in uow.germplasm.get_entries(names=[name])]

    async def unit_of_entry():
        (entry,) = await post(READ_UNIT, {'ids': [entry_id]}, 'germplasmEntries')
        return entry['unit'] and int(entry['unit']['id'])

    assert await unit_of_entry() == unit_id
    # omitted, it is unchanged
    await post(UPDATE, {'entry': {'id': entry_id, 'description': 'A selection'}}, 'germplasmUpdateEntry')
    assert await unit_of_entry() == unit_id
    await post(UPDATE, {'entry': {'id': entry_id, 'unitId': other_unit_id}}, 'germplasmUpdateEntry')
    assert await unit_of_entry() == other_unit_id
    # null removes it
    await post(UPDATE, {'entry': {'id': entry_id, 'unitId': None}}, 'germplasmUpdateEntry')
    assert await unit_of_entry() is None
