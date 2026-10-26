"""
A site beside another on the same host, under SITE_PATH with COOKIE_PREFIX, as the demonstration site can be beside
production (instance/demo/README.md): its links start with its path, and its cookies are named with the prefix and set
for its path, so the other site's cookies, which the browser sends it too, are neither read nor overwritten
"""
import pytest
from http.cookies import SimpleCookie
from httpx import AsyncClient, ASGITransport

from breedgraph.config import routing, GQL_API_PATH
from tests.breedgraph.e2e.utils import with_auth, terms_cookie, get_verified_payload

ACCOUNT = "query { accountsAccount { status result { user { id } } errors { name message } } }"


@pytest.fixture
def demo_site(monkeypatch):
    monkeypatch.setattr(routing, 'SITE_PATH', '/demo')
    monkeypatch.setattr(routing, 'COOKIE_PREFIX', 'demo_')


def test_the_site_path_is_taken_with_or_without_slashes():
    assert [routing.site_path(value) for value in ('demo', '/demo/', 'demo/', '', '/', None)] == ['/demo'] * 3 + [''] * 3


def test_links_start_with_the_site_path(demo_site, monkeypatch):
    for name, value in (('PROTOCOL', 'https'), ('HOST_ADDRESS', 'breedgraph.example.org'), ('HOST_PORT', '443'), ('VUE_PORT', '443')):
        monkeypatch.setattr(routing, name, value)
    assert routing.get_vue_url() == 'https://breedgraph.example.org/demo/'
    assert routing.get_download_endpoint() == 'https://breedgraph.example.org/demo/download?token='
    # an origin has no path
    assert routing.get_vue_origin() == 'https://breedgraph.example.org'
    assert (routing.cookie_name('auth_token'), routing.cookie_path()) == ('demo_auth_token', '/demo/')


@pytest.mark.asyncio(loop_scope="session")
async def test_the_sites_cookies_are_its_own(test_app, demo_site, login_token_factory, read_policy):
    # at the API's own address, as the proxy in front of it strips the site's path
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://localhost") as fresh:
        response = await fresh.post("/csrf")
        csrf = [SimpleCookie(header) for header in response.headers.get_list('set-cookie')]
        cookie, = [c['demo_csrf_token'] for c in csrf if 'demo_csrf_token' in c]
        assert cookie['path'] == '/demo/' and not any('csrf_token' in c for c in csrf)
        token = response.json()['token']
        user = read_policy['writer']
        auth = login_token_factory(user)

        async def account(headers: dict):
            return await fresh.post(GQL_API_PATH, json={"query": ACCOUNT}, headers=headers)

        # with the site's cookies, as with_auth names them here
        signed_in = get_verified_payload(await account(with_auth(token, auth)), 'accountsAccount')
        assert signed_in['result']['user']['id'] == str(user)
        # the other site's cookies are not the site's
        other = {"X-CSRF-Token": token, "Cookie": f"csrf_token={token}; auth_token={auth}"}
        assert (await account(other)).status_code == 403
        theirs = {"X-CSRF-Token": token, "Cookie": f"demo_csrf_token={token}; {terms_cookie(user)[len('demo_'):]}; auth_token={auth}"}
        refused = (await account(theirs)).json()
        assert [error['extensions']['code'] for error in refused['errors']] == ['TERMS_NOT_ACCEPTED']
