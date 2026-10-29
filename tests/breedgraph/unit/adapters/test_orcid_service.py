import time
from urllib.parse import urlparse, parse_qs

import pytest

from breedgraph import config
from breedgraph.adapters.orcid import OidcOrcidService
from breedgraph.adapters.orcid.orcid_service import PACKAGED_JWKS, jwks_path
from breedgraph.custom_exceptions import IllegalOperationError, UnauthorisedOperationError

from tests.breedgraph.utilities.orcid_tokens import (
    CLIENT_ID, ORCID, configure_orcid, id_token, new_key, hs256_with_public_key
)

NONCE = 'a-nonce'


@pytest.fixture
def configured(monkeypatch, tmp_path):
    configure_orcid(monkeypatch, tmp_path)


def test_not_configured(monkeypatch):
    monkeypatch.setattr(config, 'ORCID_CLIENT_ID', None)
    service = OidcOrcidService()
    assert not service.configured
    with pytest.raises(IllegalOperationError, match="not configured"):
        service.authorization_url('state', 'nonce')


def test_not_configured_without_keys(configured, monkeypatch, tmp_path):
    monkeypatch.setattr(config, 'ORCID_JWKS_PATH', str(tmp_path / 'missing.json'))
    assert not OidcOrcidService().configured


def test_authorization_url(configured):
    url = urlparse(OidcOrcidService().authorization_url('a-state', 'a-nonce'))
    assert f"{url.scheme}://{url.netloc}{url.path}" == 'https://sandbox.orcid.org/oauth/authorize'
    assert parse_qs(url.query) == {
        'client_id': [CLIENT_ID], 'response_type': ['id_token'], 'scope': ['openid'],
        'redirect_uri': ['https://breedgraph.test/orcid'], 'state': ['a-state'], 'nonce': ['a-nonce']
    }


def test_verified_orcid(configured):
    assert OidcOrcidService().verified_orcid(id_token(NONCE), NONCE) == ORCID


@pytest.mark.parametrize('token', [
    pytest.param(lambda: id_token(NONCE, aud='APP-ANOTHER'), id='another client'),
    pytest.param(lambda: id_token(NONCE, iss='https://orcid.org'), id='another issuer'),
    pytest.param(lambda: id_token(NONCE, iat=int(time.time()) - 90000, exp=int(time.time()) - 3600), id='expired'),
    pytest.param(lambda: id_token('another-nonce'), id='another nonce'),
    pytest.param(lambda: id_token(None), id='no nonce'),
    pytest.param(lambda: id_token(NONCE, sub=None), id='no subject'),
    pytest.param(lambda: id_token(NONCE, exp=None), id='no expiry'),
    pytest.param(lambda: id_token(NONCE, key_id='another-key'), id='a key not held'),
    pytest.param(lambda: id_token(NONCE, key_id=None), id='no key id'),
    pytest.param(lambda: id_token(NONCE, key=new_key()), id='signed by another key'),
    pytest.param(lambda: id_token(NONCE, key=None, algorithm='none'), id='unsigned'),
    pytest.param(lambda: hs256_with_public_key(NONCE), id='HS256 with the public key'),
    pytest.param(lambda: 'not-a-token', id='malformed'),
])
def test_verified_orcid_refused(configured, token):
    with pytest.raises(UnauthorisedOperationError, match="could not be verified"):
        OidcOrcidService().verified_orcid(token(), NONCE)


def test_packaged_keys_are_chosen_by_base_url(monkeypatch):
    monkeypatch.setattr(config, 'ORCID_JWKS_PATH', None)
    for host in ['orcid.org', 'sandbox.orcid.org']:
        monkeypatch.setattr(config, 'ORCID_BASE_URL', f'https://{host}')
        assert jwks_path() == PACKAGED_JWKS / f'{host}.json'


@pytest.mark.parametrize('host', ['orcid.org', 'sandbox.orcid.org'])
def test_packaged_keys_load(monkeypatch, host):
    monkeypatch.setattr(config, 'ORCID_CLIENT_ID', CLIENT_ID)
    monkeypatch.setattr(config, 'ORCID_JWKS_PATH', None)
    monkeypatch.setattr(config, 'ORCID_BASE_URL', f'https://{host}')
    service = OidcOrcidService()
    assert service.configured
    assert [key.key_type for key in service.keys.keys] == ['RSA']
    assert all(key.public_key_use == 'sig' for key in service.keys.keys)
