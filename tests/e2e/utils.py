from src.breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus


def with_auth(csrf_token: str, auth_token: str | None = None) -> dict:
    """Helper function to create headers with proper tokens for test requests.

    Args:
        csrf_token: The CSRF token to include in both header and cookie
        auth_token: Optional authentication token to include in cookie

    Returns:
        dict: Headers dictionary with proper CSRF and cookie values
    """
    headers = {
        "X-CSRF-Token": csrf_token,
        "Cookie": f"csrf_token={csrf_token}"
    }

    if auth_token:
        headers["Cookie"] += f"; auth_token={auth_token}"

    return headers


def get_verified_payload(response, query_name):
    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/json'
    payload = response.json()['data'][query_name]
    return payload

def assert_payload_success(payload):
    assert payload['status'] == GQLStatus.SUCCESS.name
    assert payload['errors'] is None
    assert payload['result']
