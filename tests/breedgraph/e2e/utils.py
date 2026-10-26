from functools import lru_cache

from breedgraph import config
from breedgraph.config import GQL_API_PATH
from breedgraph.adapters.its_dangerous.token_auth_service import ItsDangerousAuthService
from breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus
from breedgraph.service_layer.application.acceptance_tokens import AcceptanceTokens, Acceptances, cookie_name
from breedgraph.service_layer.application.terms_of_use import load_legal_text


@lru_cache(maxsize=1)
def acceptance_tokens() -> AcceptanceTokens:
    """Tokens signed as the API signs them, from the same configuration"""
    return AcceptanceTokens(
        secret_key=config.SECRET_KEY,
        salt=config.ACCEPTANCE_SALT,
        signed_in_minutes=config.ACCEPTANCE_EXPIRES_SIGNED_IN,
        anonymous_minutes=config.ACCEPTANCE_EXPIRES_ANONYMOUS
    )


def terms_cookie(user_id: int | None) -> str:
    """A cookie accepting the published Terms of Use for the user, or a visitor who isn't signed in, as termsAccept sets"""
    acceptances = Acceptances(user_id=user_id, terms=load_legal_text(config.TERMS_OF_USE_PATH).content_hash)
    return f"{cookie_name(user_id)}={acceptance_tokens().token(acceptances)}"


def _user_id(auth_token: str | None) -> int | None:
    try:
        login = ItsDangerousAuthService().validate_login_token(auth_token) if auth_token else None
        return login.user_id if login else None
    except Exception:  # an invalid token, which a test means to send
        return None


def with_auth(csrf_token: str, auth_token: str | None = None, accept_terms: bool = True) -> dict:
    """Helper function to create headers with proper tokens for test requests.

    Args:
        csrf_token: The CSRF token to include in both header and cookie
        auth_token: Optional authentication token to include in cookie
        accept_terms: Whether to send an acceptance of the Terms of Use for the request's user, without which the API
            refuses everything but the Terms (docs/licences.md §4)

    Returns:
        dict: Headers dictionary with proper CSRF and cookie values
    """
    headers = {
        "X-CSRF-Token": csrf_token,
        "Cookie": f"{config.cookie_name('csrf_token')}={csrf_token}"
    }

    if auth_token:
        headers["Cookie"] += f"; {config.cookie_name('auth_token')}={auth_token}"
    if accept_terms:
        # as a browser that accepted before signing in holds both: the API reads the one for whom it takes the request
        # to be from, which is the visitor's when the token's account no longer exists
        headers["Cookie"] += f"; {terms_cookie(None)}"
        user_id = _user_id(auth_token)
        if user_id is not None:
            headers["Cookie"] += f"; {terms_cookie(user_id)}"

    return headers


def get_verified_payload(response, query_name):
    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/json'
    body = response.json()
    assert body.get('data') is not None, body.get('errors')
    payload = body['data'][query_name]
    return payload

def assert_payload_success(payload):
    assert payload['status'] == GQLStatus.SUCCESS.name
    assert payload['errors'] is None
    assert payload['result']


async def post_as(client, login_token_factory, user_id: int | None, query: str, variables: dict | None = None):
    """Post a GraphQL query as the user, or anonymously when user_id is None"""
    headers = with_auth(
        csrf_token=client.headers["X-CSRF-Token"],
        auth_token=login_token_factory(user_id) if user_id is not None else None
    )
    return await client.post(GQL_API_PATH, json={"query": query, "variables": variables or {}}, headers=headers)
