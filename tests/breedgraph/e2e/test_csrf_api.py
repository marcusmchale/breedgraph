"""
The CSRF token's cookie: set for the API's own host only, as the login and acceptance cookies are, so that a site on a
subdomain of it, such as the demonstration site (instance/demo/README.md), is never sent it
"""
import pytest
from http.cookies import SimpleCookie
from httpx import AsyncClient, ASGITransport

from breedgraph.config import get_base_url


@pytest.mark.asyncio(loop_scope="session")
async def test_the_csrf_cookie_names_no_domain(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url=get_base_url()) as fresh:
        response = await fresh.post("/csrf")
    assert response.status_code == 200
    cookies = [SimpleCookie(header) for header in response.headers.get_list('set-cookie')]
    csrf = [cookie['csrf_token'] for cookie in cookies if 'csrf_token' in cookie]
    assert len(csrf) == 1
    assert csrf[0].value == response.json()['token']
    assert csrf[0]['domain'] == ''
    assert csrf[0]['httponly'] and csrf[0]['secure'] and csrf[0]['samesite'].lower() == 'strict'
