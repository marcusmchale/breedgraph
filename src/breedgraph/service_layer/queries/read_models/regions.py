from src.breedgraph.adapters.redis.read_model import ReadModel
from src.breedgraph.domain.model.regions import LocationInput

# typing imports
from typing import AsyncGenerator

async def countries(read_model: ReadModel) -> AsyncGenerator[LocationInput, None]:
    async for country in read_model.get_countries():
        yield country

