from abc import ABC, abstractmethod
from typing import Iterable, Self


class AbstractReadModels(ABC):
    """
    Read models kept in the state store, built from the database: countries now, others later.

    Refreshing a read model rebuilds it whole from the database and replaces it, so it is current
    whatever changed it (the API, a script or the migration), and stale entries go.
    Nothing else in the state store is touched, so a refresh is safe on a running instance.
    """
    names: tuple[str, ...]

    @classmethod
    @abstractmethod
    async def create(cls, *args, **kwargs) -> Self:
        ...

    async def refresh(self, names: Iterable[str] | None = None) -> None:
        """Refresh the named read models, or all of them"""
        names = list(self.names if names is None else names)
        unknown = [name for name in names if name not in self.names]
        if unknown:
            raise ValueError(f"Unknown read models {unknown}; the read models are {list(self.names)}")
        for name in names:
            await self._refresh(name)

    @abstractmethod
    async def _refresh(self, name: str) -> None:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...
