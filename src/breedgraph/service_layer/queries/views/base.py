from abc import ABC, abstractmethod
from typing import AsyncGenerator
from src.breedgraph.domain.model.accounts import UserOutput
from src.breedgraph.domain.model.controls import Access
from src.breedgraph.domain.model.regions import LocationStored

class AbstractViewsHolder(ABC):
    @abstractmethod
    async def check_any_account(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def check_allowed_email(self, email: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def access_teams(self, user: int) -> dict[Access, list[int]]:
        raise NotImplementedError

    @abstractmethod
    async def get_user(self, user: int) -> UserOutput:
        raise NotImplementedError

    @abstractmethod
    async def users_for_admin(self, user: int) -> AsyncGenerator[UserOutput, None]:
        raise NotImplementedError

    @abstractmethod
    async def get_countries(self) -> AsyncGenerator[LocationStored, None]:
        raise NotImplementedError