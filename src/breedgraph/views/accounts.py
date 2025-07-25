from src.breedgraph.service_layer import unit_of_work
from src.breedgraph.domain.model.accounts import UserOutput
from src.breedgraph.domain.model.controls import Access

from typing import AsyncGenerator

import logging
logger= logging.getLogger(__name__)

async def check_any_account(uow: unit_of_work.Neo4jUnitOfWork) -> bool:
    async with uow.get_views() as views:
        return await views.check_any_account()

async def check_allowed_email(uow: unit_of_work.AbstractUnitOfWork, email: str):
    async with uow.get_views() as views:
        return await views.check_allowed_email(email)

async def access_teams(uow: unit_of_work.AbstractUnitOfWork, user: int) -> dict[Access, list[int]]:
    async with uow.get_views() as views:
        return await views.access_teams(user)

async def users(
        uow: unit_of_work.AbstractUnitOfWork,
        user: int
) -> AsyncGenerator[UserOutput, None]:
    async with uow.get_views() as views:
        async for user_output in views.users(user):
            yield user_output
