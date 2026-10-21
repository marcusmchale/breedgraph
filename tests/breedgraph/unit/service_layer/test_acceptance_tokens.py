"""
Acceptance tokens (service_layer/application/acceptance_tokens.py, docs/licences.md §4). Fixture-free:
python -m pytest --noconftest -p no:cacheprovider tests/breedgraph/unit/service_layer/test_acceptance_tokens.py
"""
import hashlib
import time

import pytest

from breedgraph.service_layer.application import acceptance_tokens as module
from breedgraph.service_layer.application.acceptance_tokens import AcceptanceTokens, Acceptances, cookie_name

TOKENS = AcceptanceTokens(secret_key='secret', salt='acceptances', signed_in_minutes=525600, anonymous_minutes=10080)


def cookies_of(acceptances: Acceptances, tokens: AcceptanceTokens = TOKENS) -> dict[str, str]:
    return {cookie_name(acceptances.user_id): tokens.token(acceptances)}


@pytest.mark.parametrize('user_id', [None, 12])
def test_what_was_accepted_reads_back(user_id):
    acceptances = Acceptances(user_id=user_id, terms='terms-hash', licences={3: 'licence-hash'})
    read = TOKENS.read(cookies_of(acceptances), user_id)
    assert read == acceptances
    assert read.accepts_terms('terms-hash') and not read.accepts_terms('changed-terms')
    assert read.accepts_licence(3, 'licence-hash') and not read.accepts_licence(3, 'changed-text')
    assert not read.accepts_licence(4, 'licence-hash')


def test_each_identity_has_its_own_cookie_and_lifetime():
    assert TOKENS.cookie(Acceptances(user_id=None)) | {'value': None} == {
        'key': 'acceptances', 'value': None, 'max_age': 604800,
        'httponly': True, 'secure': True, 'samesite': 'strict', 'path': '/'
    }
    cookie = TOKENS.cookie(Acceptances(user_id=12))
    assert (cookie['key'], cookie['max_age']) == ('acceptances_12', 31536000)


def test_a_token_counts_only_for_its_own_identity():
    signed_in = Acceptances(user_id=12, terms='terms-hash')
    # under another user's name, or a visitor's, it is ignored
    assert TOKENS.read({'acceptances_13': TOKENS.token(signed_in)}, 13) == Acceptances(user_id=13)
    assert TOKENS.read({'acceptances': TOKENS.token(signed_in)}, None) == Acceptances(user_id=None)
    # and a visitor's acceptances don't hold for a user
    assert TOKENS.read({'acceptances_12': TOKENS.token(Acceptances(user_id=None, terms='terms-hash'))}, 12) == Acceptances(user_id=12)


def test_a_tampered_token_or_one_signed_otherwise_counts_for_nothing():
    token = TOKENS.token(Acceptances(user_id=None, terms='terms-hash'))
    assert TOKENS.read({'acceptances': token[:-2] + ('AA' if not token.endswith('AA') else 'BB')}, None) == Acceptances(user_id=None)
    other = AcceptanceTokens(secret_key='secret', salt='another salt', signed_in_minutes=525600, anonymous_minutes=10080)
    assert other.read({'acceptances': token}, None) == Acceptances(user_id=None)


def test_tokens_expire_after_their_identitys_lifetime(monkeypatch):
    anonymous = Acceptances(user_id=None, terms='terms-hash')
    signed_in = Acceptances(user_id=12, terms='terms-hash')
    now = time.time()
    monkeypatch.setattr(time, 'time', lambda: now - 8 * 86400)
    eight_days_old = {**cookies_of(anonymous), **cookies_of(signed_in)}
    monkeypatch.setattr(time, 'time', lambda: now)
    assert TOKENS.read(eight_days_old, None) == Acceptances(user_id=None)
    assert TOKENS.read(eight_days_old, 12) == signed_in


def test_the_least_recently_accepted_licences_are_dropped_to_keep_the_token_small(monkeypatch):
    monkeypatch.setattr(module, 'TOKEN_SIZE_LIMIT', 600)
    acceptances = Acceptances(user_id=12, terms='terms-hash')
    # content hashes, which hardly compress
    content_hash = lambda licence_id: hashlib.sha256(str(licence_id).encode()).hexdigest()
    for licence_id in range(1, 21):
        acceptances.accept_licence(licence_id, content_hash(licence_id))
    acceptances.accept_licence(1, content_hash(1))  # accepted again, the first becomes the most recent
    token = TOKENS.token(acceptances)
    assert len(token) <= 600
    read = TOKENS.read({'acceptances_12': token}, 12)
    assert read.terms == 'terms-hash'
    assert 0 < len(read.licences) < 20
    assert list(read.licences)[-1] == 1 and 2 not in read.licences


def test_a_salt_is_required():
    with pytest.raises(ValueError, match='ACCEPTANCE_SALT'):
        AcceptanceTokens(secret_key='secret', salt=None, signed_in_minutes=1, anonymous_minutes=1)
