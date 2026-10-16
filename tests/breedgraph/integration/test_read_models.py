import pytest

from breedgraph.adapters.redis.read_models import RedisReadModels, COUNTRY_KEY
from breedgraph.domain.model.location_trees import LocationInput


@pytest.mark.asyncio(loop_scope="session")
async def test_refresh_replaces_a_read_model_and_nothing_else(uow_factory, state_store):
    connection = state_store.connection
    await connection.hset(COUNTRY_KEY, 'XXX', '{"name": "Stale", "code": "XXX"}')
    await connection.hset('unrelated', 'kept', '1')
    try:
        read_models = await RedisReadModels.create(driver=uow_factory.driver, connection=connection)
        await read_models.refresh(['countries'])

        assert await connection.hget(COUNTRY_KEY, 'XXX') is None
        assert await connection.hget('unrelated', 'kept') == b'1'
        assert isinstance(await state_store.get_country('NIC'), LocationInput)
        assert not [key async for key in connection.scan_iter(match=f"{COUNTRY_KEY}:refresh:*")]
    finally:
        await connection.delete('unrelated')


@pytest.mark.asyncio(loop_scope="session")
async def test_refresh_rejects_unknown_read_models(uow_factory, state_store):
    read_models = await RedisReadModels.create(driver=uow_factory.driver, connection=state_store.connection)
    with pytest.raises(ValueError, match="Unknown read models"):
        await read_models.refresh(['countries', 'nothing'])
