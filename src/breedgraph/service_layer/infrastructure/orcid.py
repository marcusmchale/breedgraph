"""
Verifying a user's ORCID iD through ORCID sign-in (OAuth, scope /authenticate). See docs/person.md §6.
Only the iD is kept; ORCID's access token is discarded.
"""
from abc import ABC, abstractmethod


class AbstractOrcidService(ABC):

    @property
    @abstractmethod
    def configured(self) -> bool:
        ...

    @abstractmethod
    def authorization_url(self, state: str) -> str:
        """The ORCID sign-in page, which redirects back with a code and the given state"""
        ...

    @abstractmethod
    async def verified_orcid(self, code: str) -> str:
        """Exchange the code from ORCID sign-in for the signed-in user's ORCID iD"""
        ...
