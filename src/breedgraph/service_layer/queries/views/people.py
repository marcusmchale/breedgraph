from abc import ABC, abstractmethod

from breedgraph.domain.model.people import PersonOutput

from typing import List


class AbstractPeopleView(ABC):
    """
    Persons as the user may see them. A Person the user can read, or is linked to, is returned in full; one they
    cannot read is a placeholder when asked for by id (its id, with no name), and is left out of searches.
    """
    user_id: int | None
    read_teams: List[int]

    async def get_people(self, person_ids: List[int]) -> List[PersonOutput]:
        """The Persons with these ids that exist, in id order"""
        person_ids = [int(person_id) for person_id in dict.fromkeys(person_ids) if person_id is not None]
        if not person_ids:
            return []
        return await self._get_people(person_ids)

    @abstractmethod
    async def _get_people(self, person_ids: List[int]) -> List[PersonOutput]:
        ...

    async def search_people(self, name: str | None = None) -> List[PersonOutput]:
        """The Persons the user can read with this name, ignoring case, or all of them without a name"""
        return await self._search_people(name)

    @abstractmethod
    async def _search_people(self, name: str | None) -> List[PersonOutput]:
        ...
