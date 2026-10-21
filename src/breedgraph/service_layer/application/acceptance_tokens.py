"""
What a browser's user has accepted, the Terms of Use and study licences, kept as one signed token per identity in a
cookie (docs/licences.md §4). Nothing about who accepted what is stored, so anonymous visitors can accept too.

- The cookie is `acceptances` for a visitor who isn't signed in and `acceptances_<user id>` for a signed-in user, so a
  second person signing in on the same browser inherits nothing, and a lapsed sign-in can't overwrite an account's
  token.
- A token holds the user id (or none), the hash of the Terms accepted, and the content hash of each licence accepted,
  by licence id, least recently accepted first. An acceptance counts only while its text's hash is current.
- Tokens of signed-in users last ACCEPTANCE_EXPIRES_SIGNED_IN minutes, and those of visitors who aren't
  ACCEPTANCE_EXPIRES_ANONYMOUS: checked from the token's own time, and set as the cookie's lifetime. Each acceptance
  reissues the token, which renews it.
- A cookie holds 4 KB, so a token is kept under TOKEN_SIZE_LIMIT by dropping the least recently accepted licences,
  which are then asked for again.
"""
from dataclasses import dataclass, field
from typing import Mapping

from itsdangerous import URLSafeTimedSerializer, BadSignature

COOKIE_NAME = 'acceptances'
TOKEN_SIZE_LIMIT = 3500


def cookie_name(user_id: int | None) -> str:
    return COOKIE_NAME if user_id is None else f'{COOKIE_NAME}_{user_id}'


@dataclass
class Acceptances:
    """What one identity, a user or a visitor who isn't signed in, has accepted"""
    user_id: int | None
    # the hash of the Terms of Use accepted
    terms: str | None = None
    # licence id: the content hash accepted, least recently accepted first
    licences: dict[int, str] = field(default_factory=dict)

    def accepts_terms(self, terms_hash: str) -> bool:
        return self.terms is not None and self.terms == terms_hash

    def accepts_licence(self, licence_id: int, content_hash: str | None) -> bool:
        return content_hash is not None and self.licences.get(licence_id) == content_hash

    def accept_licence(self, licence_id: int, content_hash: str) -> None:
        # accepted again, it becomes the most recent
        self.licences.pop(licence_id, None)
        self.licences[licence_id] = content_hash


class AcceptanceTokens:
    def __init__(self, secret_key: str, salt: str, signed_in_minutes: int, anonymous_minutes: int):
        if not salt:
            raise ValueError("ACCEPTANCE_SALT is required, to sign acceptances of the Terms of Use and licences")
        self._serializer = URLSafeTimedSerializer(secret_key, salt=salt)
        self.signed_in_minutes = signed_in_minutes
        self.anonymous_minutes = anonymous_minutes

    def lifetime_seconds(self, user_id: int | None) -> int:
        return (self.anonymous_minutes if user_id is None else self.signed_in_minutes) * 60

    def read(self, cookies: Mapping[str, str], user_id: int | None) -> Acceptances:
        """The acceptances of the identity, from its cookie: none when it has none, or it isn't valid for them"""
        token = cookies.get(cookie_name(user_id))
        if not token:
            return Acceptances(user_id)
        try:
            data = self._serializer.loads(token, max_age=self.lifetime_seconds(user_id))
        except BadSignature:  # tampered, signed with another key or salt, or expired
            return Acceptances(user_id)
        if not isinstance(data, dict) or data.get('u') != user_id:
            return Acceptances(user_id)
        return Acceptances(
            user_id=user_id,
            terms=data.get('t'),
            licences={int(licence_id): content_hash for licence_id, content_hash in data.get('l') or []}
        )

    def token(self, acceptances: Acceptances) -> str:
        """The signed token, within TOKEN_SIZE_LIMIT: the least recently accepted licences are dropped to fit"""
        licences = list(acceptances.licences.items())
        while True:
            token = self._serializer.dumps({'u': acceptances.user_id, 't': acceptances.terms, 'l': licences})
            if len(token) <= TOKEN_SIZE_LIMIT or not licences:
                return token
            licences = licences[1:]

    def cookie(self, acceptances: Acceptances) -> dict:
        """The cookie holding the token, for the response, set as the auth_token cookie is"""
        return {
            "key": cookie_name(acceptances.user_id),
            "value": self.token(acceptances),
            "max_age": self.lifetime_seconds(acceptances.user_id),
            "httponly": True,
            "secure": True,
            "samesite": "strict",
            "path": "/"
        }
