from abc import ABC, abstractmethod

from breedgraph.domain.model.people import PersonOutput

from typing import Dict, List


class AbstractPeopleView(ABC):
    """
    Persons as the user may see them (docs/person.md §3): in full to read affiliates of a controlling team and to the
    linked user, by attribution to those reading them by release only, and otherwise restricted, as an id with its
    data controller, when asked for by id. Searches leave restricted Persons out.
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

    async def get_people_by_users(self, user_ids: List[int]) -> Dict[int, PersonOutput]:
        """The Persons linked to these accounts, by account id; accounts without a Person are left out"""
        user_ids = [int(user_id) for user_id in dict.fromkeys(user_ids) if user_id is not None]
        if not user_ids:
            return {}
        return await self._get_people_by_users(user_ids)

    @abstractmethod
    async def _get_people_by_users(self, user_ids: List[int]) -> Dict[int, PersonOutput]:
        ...

    async def search_people(self, name: str | None = None) -> List[PersonOutput]:
        """The Persons the user can see in full or by attribution with this name, ignoring case, or all of them"""
        return await self._search_people(name)

    @abstractmethod
    async def _search_people(self, name: str | None) -> List[PersonOutput]:
        ...
