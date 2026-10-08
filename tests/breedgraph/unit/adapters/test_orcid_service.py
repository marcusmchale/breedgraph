from urllib.parse import urlparse, parse_qs

import httpx
import pytest

from breedgraph import config
from breedgraph.adapters.orcid import orcid_service as orcid_module
from breedgraph.adapters.orcid import HttpxOrcidService
from breedgraph.custom_exceptions import IllegalOperationError, UnauthorisedOperationError


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(config, 'ORCID_CLIENT_ID', 'APP-TEST')
    monkeypatch.setattr(config, 'ORCID_CLIENT_SECRET', 'secret')
    monkeypatch.setattr(config, 'ORCID_BASE_URL', 'https://sandbox.orcid.org')
    monkeypatch.setattr(config, 'ORCID_REDIRECT_URI', 'https://breedgraph.test/orcid')


def mock_orcid(monkeypatch, status: int, body: dict, requests: list):
    def handle(request: httpx.Request):
        requests.append(request)
        return httpx.Response(status, json=body)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(orcid_module.httpx, 'AsyncClient', lambda **kwargs: real_client(transport=httpx.MockTransport(handle)))


def test_not_configured(monkeypatch):
    monkeypatch.setattr(config, 'ORCID_CLIENT_ID', None)
    service = HttpxOrcidService()
    assert not service.configured
    with pytest.raises(IllegalOperationError, match="not configured"):
        service.authorization_url('state')


def test_authorization_url(configured):
    url = urlparse(HttpxOrcidService().authorization_url('a-state'))
    assert f"{url.scheme}://{url.netloc}{url.path}" == 'https://sandbox.orcid.org/oauth/authorize'
    assert parse_qs(url.query) == {
        'client_id': ['APP-TEST'], 'response_type': ['code'], 'scope': ['/authenticate'],
        'redirect_uri': ['https://breedgraph.test/orcid'], 'state': ['a-state']
    }


@pytest.mark.asyncio
async def test_verified_orcid(configured, monkeypatch):
    requests = []
    mock_orcid(monkeypatch, 200, {'access_token': 'token', 'name': 'A Person', 'orcid': '0000-0002-1825-0097'}, requests)
    assert await HttpxOrcidService().verified_orcid('a-code') == '0000-0002-1825-0097'
    [request] = requests
    assert str(request.url) == 'https://sandbox.orcid.org/oauth/token'
    assert parse_qs(request.content.decode()) == {
        'client_id': ['APP-TEST'], 'client_secret': ['secret'], 'grant_type': ['authorization_code'],
        'code': ['a-code'], 'redirect_uri': ['https://breedgraph.test/orcid']
    }


@pytest.mark.asyncio
async def test_verified_orcid_refused(configured, monkeypatch):
    mock_orcid(monkeypatch, 400, {'error': 'invalid_grant'}, [])
    with pytest.raises(UnauthorisedOperationError):
        await HttpxOrcidService().verified_orcid('a-code')
