def get_verified_payload(response, query_name):
    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/json'
    payload = response.json()['data'][query_name]
    return payload
