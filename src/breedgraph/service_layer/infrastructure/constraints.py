from abc import ABC, abstractmethod

class AbstractConstraintsHandler(ABC):
    user_id: int|None = None

    @abstractmethod
    async def accounts_exist(self) -> bool:
        ...

    @abstractmethod
    async def is_ontology_admin(self) -> bool:
        ...

    @abstractmethod
    async def is_last_ontology_admin(self) -> bool:
        ...
    @abstractmethod
    async def sole_admin_teams(self) -> list[int]:
        """Teams with no authorised admin besides the user"""
        ...
