"""
/download serves a file for a token issued by referencesFileDownload. A token tampered with, signed for something else
or not a token at all is refused as invalid (401), as an expired one is refused as expired, rather than failing with
a server error.
"""
import pytest
from itsdangerous import URLSafeTimedSerializer

from breedgraph.config import SECRET_KEY, FILE_DOWNLOAD_SALT
from breedgraph.entrypoints.fastapi import downloads


def download_token(salt: str = FILE_DOWNLOAD_SALT, **details) -> str:
    return URLSafeTimedSerializer(SECRET_KEY).dumps(details, salt=salt)


def tampered(token: str) -> str:
    return token[:-4] + ('AAAA' if not token.endswith('AAAA') else 'BBBB')


async def refusal(client, token: str) -> tuple[int, str]:
    response = await client.get('/download', params={'token': token})
    return response.status_code, response.json()['detail']


@pytest.mark.asyncio(loop_scope="session")
async def test_a_token_not_issued_for_a_download_is_invalid(client):
    issued = download_token(uuid='some-file', filename='data.csv', contentType='text/csv')
    for token in (
            tampered(issued),
            download_token(salt='another purpose', uuid='some-file'),
            'not-a-token',
            download_token(filename='data.csv')  # names no file
    ):
        assert await refusal(client, token) == (401, "Invalid download token"), token


@pytest.mark.asyncio(loop_scope="session")
async def test_an_expired_token_is_refused_as_expired(client, monkeypatch):
    monkeypatch.setattr(downloads, 'FILE_DOWNLOAD_EXPIRES', -1)
    token = download_token(uuid='some-file', filename='data.csv', contentType='text/csv')
    assert await refusal(client, token) == (401, "Download token has expired")
