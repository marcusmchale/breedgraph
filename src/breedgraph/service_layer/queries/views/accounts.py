from abc import ABC, abstractmethod
from typing import AsyncGenerator

from src.breedgraph.domain.model.accounts import UserOutput

from typing import List

class AbstractAccountsViews(ABC):

    @abstractmethod
    async def check_any_account(self) -> bool:
        ...

    @abstractmethod
    async def check_allowed_email(self, email: str) -> bool:
        ...

    @abstractmethod
    async def get_user(self, user_id: int) -> UserOutput:
        ...

    @abstractmethod
    def get_users_for_admin(self, team_ids: List[int], user_ids: List[int]) -> AsyncGenerator[UserOutput, None]:
        ...