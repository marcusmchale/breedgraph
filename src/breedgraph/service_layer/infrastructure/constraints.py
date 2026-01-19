from abc import ABC, abstractmethod
from src.breedgraph.domain.model.accounts import OntologyRole

class AbstractConstraintsHandler(ABC):
    user_id: int = None

    @abstractmethod
    async def accounts_exist(self) -> bool:
        ...

    @abstractmethod
    async def email_allowed(self, email: str) -> bool:
        ...

    @abstractmethod
    async def is_ontology_admin(self) -> bool:
        ...

    @abstractmethod
    async def is_last_ontology_admin(self) -> bool:
        ...