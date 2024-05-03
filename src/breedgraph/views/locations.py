from src.breedgraph.adapters.redis.read_model import ReadModel
from src.breedgraph.domain.model.locations import Country

# typing imports
from typing import AsyncGenerator

async def countries(read_model: ReadModel) -> AsyncGenerator[Country, None]:
    async for country in read_model.get_countries():
        yield country

