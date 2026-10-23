"""
The Terms of Use, accepted by everyone before anything else (docs/licences.md §4): the gate on every GraphQL operation
but the Terms and the privacy notice, termsOfUse and termsAccept, the acceptance cookies of visitors and of users, and
their carrying over at sign-in
"""
import bcrypt
import pytest
from http.cookies import SimpleCookie

from breedgraph.config import GQL_API_PATH
from breedgraph.domain.model.accounts import UserInput, AccountInput
from breedgraph.service_layer.application.terms_of_use import LegalText
from tests.breedgraph.e2e.utils import with_auth, get_verified_payload

TERMS = "query { termsOfUse { status result { text contentHash accepted } errors { message } } }"
ACCEPT = "mutation ($hash: String!) { termsAccept(contentHash: $hash) { status result errors { message } } }"
PRIVACY_NOTICE = "query { privacyNotice { status result { text contentHash } errors { message } } }"
SOMETHING_ELSE = "query { references(ids: []) { status errors { message } } }"


def cookie_header(csrf_token: str, **cookies: str | None) -> dict:
    """Headers with the CSRF token and exactly these cookies"""
    parts = [f"csrf_token={csrf_token}"] + [f"{name}={value}" for name, value in cookies.items() if value]
    return {"X-CSRF-Token": csrf_token, "Cookie": "; ".join(parts)}


def set_cookies(response) -> dict[str, dict]:
    """The cookies a response sets, by name: their value and attributes"""
    cookies = {}
    for header in response.headers.get_list('set-cookie'):
        parsed = SimpleCookie(header)
        for name, morsel in parsed.items():
            attributes = {key: morsel[key] for key in ('max-age', 'path', 'samesite') if morsel[key]}
            attributes |= {key: True for key in ('httponly', 'secure') if morsel[key]}
            cookies[name] = {'value': morsel.value, **attributes}
    return cookies


def refused_for_terms(response) -> bool:
    assert response.status_code == 200
    body = response.json()
    return body.get('data') is None and [error['extensions']['code'] for error in body['errors']] == ['TERMS_NOT_ACCEPTED']


async def post(client, headers: dict, query: str, variables: dict | None = None):
    return await client.post(GQL_API_PATH, json={"query": query, "variables": variables or {}}, headers=headers)


@pytest.mark.asyncio(loop_scope="session")
async def test_only_the_terms_and_the_privacy_notice_are_open_until_the_terms_are_accepted(client, test_app):
    headers = with_auth(client.headers["X-CSRF-Token"], accept_terms=False)

    terms = get_verified_payload(await post(client, headers, TERMS), "termsOfUse")['result']
    assert terms['text'].startswith('# BreedGraph Terms of Use')
    assert terms['contentHash'] == test_app.terms_of_use.content_hash
    assert terms['accepted'] is False

    # the Terms point to the privacy notice, so it is read before they are accepted
    notice = get_verified_payload(await post(client, headers, PRIVACY_NOTICE), "privacyNotice")['result']
    assert notice['text'] == test_app.privacy_notice.text and notice['text'].startswith('# BreedGraph privacy notice')
    assert notice['contentHash'] == test_app.privacy_notice.content_hash

    introspection = await post(client, headers, "query { __schema { queryType { name } } }")
    assert introspection.json()['data']['__schema']['queryType']['name'] == 'Query'

    assert refused_for_terms(await post(client, headers, SOMETHING_ELSE))
    # nothing else may come with the Terms
    assert refused_for_terms(await post(client, headers, "query { termsOfUse { status } references(ids: []) { status } }"))
    # nor with a mutation
    assert refused_for_terms(await post(client, headers, "mutation { referencesDelete(ids: []) { status } }"))


@pytest.mark.asyncio(loop_scope="session")
async def test_a_visitor_accepts_the_current_terms_for_a_week(client, test_app):
    csrf_token = client.headers["X-CSRF-Token"]
    headers = cookie_header(csrf_token)

    stale = get_verified_payload(await post(client, headers, ACCEPT, {'hash': 'an earlier text'}), "termsAccept")
    assert stale['status'] == 'ERROR' and 'have changed' in stale['errors'][0]['message']

    response = await post(client, headers, ACCEPT, {'hash': test_app.terms_of_use.content_hash})
    assert get_verified_payload(response, "termsAccept")['status'] == 'SUCCESS'
    cookie = set_cookies(response)['acceptances']
    assert {key: value for key, value in cookie.items() if key != 'value'} == {
        'max-age': '604800', 'path': '/', 'samesite': 'strict', 'httponly': True, 'secure': True
    }

    accepted = cookie_header(csrf_token, acceptances=cookie['value'])
    assert get_verified_payload(await post(client, accepted, SOMETHING_ELSE), "references")['status'] == 'SUCCESS'
    assert get_verified_payload(await post(client, accepted, TERMS), "termsOfUse")['result']['accepted'] is True


@pytest.mark.asyncio(loop_scope="session")
async def test_a_users_acceptance_holds_for_them_alone(client, test_app, reference_build_context, login_token_factory, uow_factory):
    from tests.breedgraph.scenarios.account_builder import AccountBuilder

    csrf_token = client.headers["X-CSRF-Token"]
    user_id = reference_build_context['user_id']
    other_id = await AccountBuilder(uow_factory=uow_factory).account()
    token, other_token = login_token_factory(user_id), login_token_factory(other_id)

    response = await post(client, cookie_header(csrf_token, auth_token=token), ACCEPT, {'hash': test_app.terms_of_use.content_hash})
    cookie = set_cookies(response)[f'acceptances_{user_id}']
    assert cookie['max-age'] == '31536000'
    value = cookie['value']

    mine = cookie_header(csrf_token, auth_token=token, **{f'acceptances_{user_id}': value})
    assert get_verified_payload(await post(client, mine, SOMETHING_ELSE), "references")['status'] == 'SUCCESS'
    # signed out, or signed in as someone else, the same browser has not accepted them
    assert refused_for_terms(await post(client, cookie_header(csrf_token, **{f'acceptances_{user_id}': value}), SOMETHING_ELSE))
    assert refused_for_terms(await post(client, cookie_header(csrf_token, auth_token=other_token, **{f'acceptances_{user_id}': value}), SOMETHING_ELSE))
    assert refused_for_terms(await post(client, cookie_header(csrf_token, auth_token=other_token, **{f'acceptances_{other_id}': value}), SOMETHING_ELSE))


@pytest.mark.asyncio(loop_scope="session")
async def test_signing_in_carries_the_terms_over(client, test_app, uow_factory, user_input_generator):
    user_input = user_input_generator.new_user_input()
    async with uow_factory.get_uow() as uow:
        account = await uow.repositories.accounts.create(AccountInput(user=UserInput(
            name=user_input['name'], fullname=user_input['name'], email=user_input['email'],
            password_hash=bcrypt.hashpw(user_input['password'].encode(), bcrypt.gensalt()).decode(),
            email_verified=True
        )))
        await uow.commit()
        user_id = account.user.id

    csrf_token = client.headers["X-CSRF-Token"]
    visitor = set_cookies(await post(client, cookie_header(csrf_token), ACCEPT, {'hash': test_app.terms_of_use.content_hash}))['acceptances']['value']
    login = await post(
        client, cookie_header(csrf_token, acceptances=visitor),
        "mutation ($u: String!, $p: String!) { accountsLogin(username: $u, password: $p) { status errors { message } } }",
        {'u': user_input['name'], 'p': user_input['password']}
    )
    assert get_verified_payload(login, "accountsLogin")['status'] == 'SUCCESS'
    cookies = set_cookies(login)
    signed_in = cookie_header(csrf_token, auth_token=cookies['auth_token']['value'], **{f'acceptances_{user_id}': cookies[f'acceptances_{user_id}']['value']})
    assert get_verified_payload(await post(client, signed_in, TERMS), "termsOfUse")['result']['accepted'] is True


@pytest.mark.asyncio(loop_scope="session")
async def test_changed_terms_are_asked_for_again(client, test_app, monkeypatch):
    headers = with_auth(client.headers["X-CSRF-Token"])  # an acceptance of the published Terms
    assert get_verified_payload(await post(client, headers, SOMETHING_ELSE), "references")['status'] == 'SUCCESS'
    monkeypatch.setattr(test_app, 'terms_of_use', LegalText(text='# Changed Terms', content_hash='changed'))
    assert refused_for_terms(await post(client, headers, SOMETHING_ELSE))
