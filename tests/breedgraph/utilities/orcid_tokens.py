"""id_tokens as ORCID signs them, with a key made here and held as ORCID's for the tests (ORCID_JWKS_PATH)"""
import base64
import hashlib
import hmac
import json
import time

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from breedgraph import config

CLIENT_ID = 'APP-TEST'
ISSUER = 'https://sandbox.orcid.org'
KEY_ID = 'test-key'
ORCID = '0000-0002-1825-0097'


def new_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


SIGNING_KEY = new_key()


def write_jwks(path, key: rsa.RSAPrivateKey = SIGNING_KEY, key_id: str = KEY_ID):
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
    path.write_text(json.dumps({'keys': [{**jwk, 'kid': key_id, 'use': 'sig'}]}))
    return path


def configure_orcid(monkeypatch, tmp_path) -> None:
    """ORCID sign-in by the sandbox's client, with the key made here held as ORCID's"""
    monkeypatch.setattr(config, 'ORCID_CLIENT_ID', CLIENT_ID)
    monkeypatch.setattr(config, 'ORCID_BASE_URL', ISSUER)
    monkeypatch.setattr(config, 'ORCID_REDIRECT_URI', 'https://breedgraph.test/orcid')
    monkeypatch.setattr(config, 'ORCID_JWKS_PATH', str(write_jwks(tmp_path / 'jwks.json')))


def id_token(nonce: str | None, key=SIGNING_KEY, key_id: str | None = KEY_ID, algorithm='RS256', **claims) -> str:
    """An id_token as ORCID signs one, with any claims given in place of its own, or left out where None"""
    now = int(time.time())
    payload = {
        'iss': ISSUER, 'aud': CLIENT_ID, 'sub': ORCID, 'nonce': nonce, 'iat': now, 'exp': now + 86400,
        'auth_time': now, 'given_name': 'A', 'family_name': 'Person', 'amr': 'pwd'
    }
    payload.update(claims)
    payload = {name: value for name, value in payload.items() if value is not None}
    headers = {'kid': key_id} if key_id else {}
    return jwt.encode(payload, key, algorithm=algorithm, headers=headers)


def hs256_with_public_key(nonce: str) -> str:
    """Signed with ORCID's public key as an HMAC secret, which anyone could do. PyJWT refuses to, so made by hand."""
    def encode(part: bytes) -> str:
        return base64.urlsafe_b64encode(part).rstrip(b'=').decode()
    _, payload, _ = id_token(nonce).split('.')
    header = encode(json.dumps({'alg': 'HS256', 'kid': KEY_ID}).encode())
    public_key = SIGNING_KEY.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    signature = hmac.new(public_key, f"{header}.{payload}".encode(), hashlib.sha256).digest()
    return f"{header}.{payload}.{encode(signature)}"
