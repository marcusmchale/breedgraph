from src.breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus


def get_verified_payload(response, query_name):
    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/json'
    payload = response.json()['data'][query_name]
    return payload

def assert_payload_success(payload):
    assert payload['status'] == GQLStatus.SUCCESS.name
    assert payload['errors'] is None
    assert payload['result']
