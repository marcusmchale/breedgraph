"""
Verifying a user's ORCID iD through ORCID sign-in (OpenID Connect implicit, scope openid). See docs/person.md §6.
ORCID gives the browser an id_token it signed, which is checked against ORCID's key held on the server, so the API
never contacts ORCID. Only the iD is kept.
"""
from abc import ABC, abstractmethod


class AbstractOrcidService(ABC):

    @property
    @abstractmethod
    def configured(self) -> bool:
        ...

    @abstractmethod
    def authorization_url(self, state: str, nonce: str) -> str:
        """The ORCID sign-in page, which redirects back with the given state and an id_token holding the nonce"""
        ...

    @abstractmethod
    def verified_orcid(self, id_token: str, nonce: str) -> str:
        """The signed-in user's ORCID iD, from an id_token ORCID signed for this client with the given nonce"""
        ...
