from src.breedgraph.domain.model.organisations import Access
from src.breedgraph.service_layer import unit_of_work


async def access_teams(uow: unit_of_work.AbstractUnitOfWork, user: int) -> dict[Access, list[int]]:
    async with uow.get_views() as views:
        return await views.access_teams(user)
