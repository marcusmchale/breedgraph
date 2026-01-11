from src.breedgraph.adapters.redis.state_store import RedisStateStore
from src.breedgraph.domain.model.regions import LocationInput

# typing imports
from typing import AsyncGenerator

async def countries(state_store: RedisStateStore) -> AsyncGenerator[LocationInput, None]:
    async for country in state_store.get_countries():
        yield country

