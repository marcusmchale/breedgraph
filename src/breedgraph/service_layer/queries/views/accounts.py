from abc import ABC, abstractmethod
from typing import AsyncGenerator

from src.breedgraph.domain.model.accounts import UserOutput
from src.breedgraph.domain.model.accounts import OntologyRole

from typing import List

from src.breedgraph.custom_exceptions import IllegalOperationError, UnauthorisedOperationError

class AbstractAccountsView(ABC):
    user_id: int | None = None

    admin_teams: List[int] | None = None
    read_teams: List[int] | None = None
    ontology_role: OntologyRole | None = None

    @abstractmethod
    async def check_any_account(self) -> bool:
        ...

    @abstractmethod
    async def check_allowed_email(self, email: str) -> bool:
        ...

    async def get_user(self) -> UserOutput|None:
        if not self.user_id:
            return None
        return await self._get_user()

    @abstractmethod
    async def _get_user(self) -> UserOutput:
        ...

    async def get_ontology_role(self) -> OntologyRole:
        if self.ontology_role is None:
            if self.user_id is None:
                self.ontology_role = OntologyRole.VIEWER
            else:
                self.ontology_role = await self._get_ontology_role()
        return self.ontology_role

    async def _get_ontology_role(self) -> OntologyRole:
        ...

    async def get_admin_teams(self) -> List[int]:
        if self.user_id is None:
            return []
        if self.admin_teams is None:
            self.admin_teams = await self._get_admin_teams()
        return self.admin_teams

    @abstractmethod
    async def _get_admin_teams(self) -> List[int]:
        ...

    async def get_read_teams(self) -> List[int]:
        if self.user_id is None:
            return []
        if self.read_teams is None:
            self.read_teams = await self._get_read_teams()
        return self.read_teams

    @abstractmethod
    async def _get_read_teams(self) -> List[int]:
        ...

    async def get_users_for_admin(
            self,
            user_ids: List[int]
    ) ->List[UserOutput]:
        admin_teams = await self.get_admin_teams()
        return [user async for user in self._get_users_for_admin(user_ids, admin_teams)]

    @abstractmethod
    def _get_users_for_admin(self, user_ids: List[int], admin_teams: List[int]) -> AsyncGenerator[UserOutput, None]:
        ...

    async def get_users_with_ontology_role_requests(self) -> List[UserOutput]:
        ontology_role = await self.get_ontology_role()
        if ontology_role != OntologyRole.ADMIN:
            raise UnauthorisedOperationError("Only ontology admins can see users with ontology role requests")
        return [ user async for user in self._get_users_with_ontology_role_requests()]

    @abstractmethod
    def _get_users_with_ontology_role_requests(self) -> AsyncGenerator[UserOutput, None]:
        ...

    async def get_editors_for_ontology_admin(self) -> List[UserOutput]:
        ontology_role = await self.get_ontology_role()
        if ontology_role != OntologyRole.ADMIN:
            raise UnauthorisedOperationError("Only ontology admins can see ontology editors")
        return [user async for user in self._get_editors_for_ontology_admin()]


    @abstractmethod
    def _get_editors_for_ontology_admin(self) -> AsyncGenerator[UserOutput, None]:
        ...

    async def get_admins_for_ontology_admin(self) -> List[UserOutput]:
        ontology_role = await self.get_ontology_role()
        if ontology_role != OntologyRole.ADMIN:
            raise UnauthorisedOperationError("Only ontology admins can see ontology admins")

        return [user async for user in self._get_admins_for_ontology_admin()]

    @abstractmethod
    def _get_admins_for_ontology_admin(self) -> AsyncGenerator[UserOutput, None]:
        ...