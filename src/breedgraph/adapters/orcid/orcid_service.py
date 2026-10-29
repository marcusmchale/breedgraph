import json
import secrets
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlencode, urlparse

import jwt

from breedgraph import config
from breedgraph.custom_exceptions import IllegalOperationError, UnauthorisedOperationError
from breedgraph.service_layer.infrastructure.orcid import AbstractOrcidService

import logging
logger = logging.getLogger(__name__)

# The keys of orcid.org and the sandbox, as ORCID publishes them (scripts/orcid_jwks.py)
PACKAGED_JWKS = Path(__file__).parent / 'jwks'
# For a difference between ORCID's clock and ours
LEEWAY_SECONDS = 60
NOT_VERIFIED = "ORCID sign-in could not be verified, please try again"


def jwks_path() -> Path:
    """The key set named by ORCID_JWKS_PATH, or else the one packaged for ORCID_BASE_URL"""
    if config.ORCID_JWKS_PATH:
        return Path(config.ORCID_JWKS_PATH)
    return PACKAGED_JWKS / f"{urlparse(config.ORCID_BASE_URL).hostname}.json"


@lru_cache
def _read_keys(path: Path) -> jwt.PyJWKSet | None:
    """Read once, so that a set missing or unreadable is logged once"""
    try:
        return jwt.PyJWKSet.from_dict(json.loads(path.read_text()))
    except (OSError, ValueError, jwt.PyJWKSetError) as e:
        logger.warning(f"Linking an ORCID iD is not available: ORCID's keys could not be read from {path}: {e}")
        return None


class OidcOrcidService(AbstractOrcidService):
    """ORCID sign-in by OpenID Connect implicit, reading the settings when used. It contacts no one."""

    @property
    def keys(self) -> jwt.PyJWKSet | None:
        return _read_keys(jwks_path())

    @property
    def configured(self) -> bool:
        return bool(config.ORCID_CLIENT_ID) and self.keys is not None

    def _require_configured(self) -> None:
        if not self.configured:
            raise IllegalOperationError("Linking an ORCID iD is not available: ORCID sign-in is not configured")

    def authorization_url(self, state: str, nonce: str) -> str:
        self._require_configured()
        query = urlencode({
            'client_id': config.ORCID_CLIENT_ID,
            # ORCID adds an access token to the fragment as well, which the front end leaves unused
            'response_type': 'id_token',
            'scope': 'openid',
            'redirect_uri': config.ORCID_REDIRECT_URI,
            'state': state,
            'nonce': nonce
        })
        return f"{config.ORCID_BASE_URL}/oauth/authorize?{query}"

    def verified_orcid(self, id_token: str, nonce: str) -> str:
        self._require_configured()
        try:
            key_id = jwt.get_unverified_header(id_token).get('kid')
        except jwt.InvalidTokenError as e:
            logger.warning(f"ORCID's id_token was refused: {e}")
            raise UnauthorisedOperationError(NOT_VERIFIED)
        try:
            key = self.keys[key_id]
        except KeyError:
            logger.warning(
                f"ORCID signed with key {key_id}, which BreedGraph doesn't hold: refresh ORCID's keys "
                f"(docs/deployment.md, ORCID linking)"
            )
            raise UnauthorisedOperationError(NOT_VERIFIED)
        # ORCID's id_tokens last a day, so what limits their use is the nonce, issued with a state that lasts minutes
        try:
            claims = jwt.decode(
                id_token,
                key,
                algorithms=['RS256'],
                audience=config.ORCID_CLIENT_ID,
                issuer=config.ORCID_BASE_URL.rstrip('/'),
                leeway=LEEWAY_SECONDS,
                options={'require': ['exp', 'iat', 'iss', 'aud', 'sub', 'nonce']}
            )
        except jwt.InvalidTokenError as e:
            logger.warning(f"ORCID's id_token was refused: {e}")
            raise UnauthorisedOperationError(NOT_VERIFIED)
        if not secrets.compare_digest(str(claims['nonce']), nonce):
            logger.warning("ORCID's id_token was refused: its nonce is not the one issued with the state")
            raise UnauthorisedOperationError(NOT_VERIFIED)
        # The id_token also holds the user's name, which is not kept
        return claims['sub']
