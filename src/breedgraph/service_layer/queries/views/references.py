from abc import ABC, abstractmethod

from breedgraph.domain.model.references import ReferenceStoredBase, ReferenceType
from breedgraph.service_layer.application.licence_seed import STANDARD_LICENCES

from typing import List


class AbstractReferencesView(ABC):
    """
    References as the user may see them. A reference the user can read is returned in full; one they cannot is a
    placeholder when asked for by id (its id, its type and a REDACTED description), and is left out of searches.
    """
    user_id: int | None
    read_teams: List[int]

    async def get_references(self, reference_ids: List[int]) -> List[ReferenceStoredBase]:
        """The references with these ids that exist, in id order"""
        reference_ids = [int(reference_id) for reference_id in dict.fromkeys(reference_ids) if reference_id is not None]
        if not reference_ids:
            return []
        return await self._get_references(reference_ids)

    @abstractmethod
    async def _get_references(self, reference_ids: List[int]) -> List[ReferenceStoredBase]:
        ...

    async def get_standard_licences(self) -> List[ReferenceStoredBase]:
        """
        The standard licences seeded in every deployment, CC BY 4.0 then CC0 1.0 (docs/licences.md §6): fixed legal
        references, which everyone reads in full; those missing from a database set up before them are left out
        """
        ids = await self._get_seeded_ids([licence.seed_key for licence in STANDARD_LICENCES])
        by_id = {reference.id: reference for reference in await self.get_references(list(ids.values()))}
        return [by_id[ids[licence.seed_key]] for licence in STANDARD_LICENCES if ids.get(licence.seed_key) in by_id]

    @abstractmethod
    async def _get_seeded_ids(self, seed_keys: List[str]) -> dict[str, int]:
        """The ids of the references seeded with these keys, by key"""
        ...

    async def get_file_reference(self, file_id: str) -> ReferenceStoredBase | None:
        """
        The file reference for a file in the store, None when there is none; a placeholder, without the file id,
        when the user cannot read it
        """
        return await self._get_file_reference(file_id)

    @abstractmethod
    async def _get_file_reference(self, file_id: str) -> ReferenceStoredBase | None:
        ...

    async def search_references(
            self,
            description: str,
            reference_types: List[ReferenceType] | None = None
    ) -> List[ReferenceStoredBase]:
        """The references the user can read whose description matches, best first"""
        return await self._search_references(description, reference_types)

    @abstractmethod
    async def _search_references(
            self,
            description: str,
            reference_types: List[ReferenceType] | None
    ) -> List[ReferenceStoredBase]:
        ...
