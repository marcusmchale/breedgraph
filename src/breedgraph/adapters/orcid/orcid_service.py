from urllib.parse import urlencode

import httpx

from breedgraph import config
from breedgraph.custom_exceptions import IllegalOperationError, UnauthorisedOperationError
from breedgraph.service_layer.infrastructure.orcid import AbstractOrcidService

import logging
logger = logging.getLogger(__name__)


class HttpxOrcidService(AbstractOrcidService):
    """ORCID Public API, reading the settings when used"""

    @property
    def configured(self) -> bool:
        return bool(config.ORCID_CLIENT_ID and config.ORCID_CLIENT_SECRET)

    def _require_configured(self) -> None:
        if not self.configured:
            raise IllegalOperationError("Linking an ORCID iD is not available: ORCID credentials are not configured")

    def authorization_url(self, state: str) -> str:
        self._require_configured()
        query = urlencode({
            'client_id': config.ORCID_CLIENT_ID,
            'response_type': 'code',
            'scope': '/authenticate',
            'redirect_uri': config.ORCID_REDIRECT_URI,
            'state': state
        })
        return f"{config.ORCID_BASE_URL}/oauth/authorize?{query}"

    async def verified_orcid(self, code: str) -> str:
        self._require_configured()
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{config.ORCID_BASE_URL}/oauth/token",
                data={
                    'client_id': config.ORCID_CLIENT_ID,
                    'client_secret': config.ORCID_CLIENT_SECRET,
                    'grant_type': 'authorization_code',
                    'code': code,
                    'redirect_uri': config.ORCID_REDIRECT_URI
                },
                headers={'Accept': 'application/json'}
            )
        if response.status_code != 200:
            logger.warning(f"ORCID token exchange failed with status {response.status_code}")
            raise UnauthorisedOperationError("ORCID sign-in could not be verified, please try again")
        # The response also holds an access token and the user's name, which are not kept
        orcid = response.json().get('orcid')
        if not orcid:
            raise UnauthorisedOperationError("ORCID sign-in did not return an ORCID iD")
        return orcid
