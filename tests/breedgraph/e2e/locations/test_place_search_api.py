"""
Place searches for the location map, asked of the geocoder (Nominatim) by the server, so browsers contact no third
party. Here the geocoder is a fake on the app; tests/breedgraph/unit/adapters/test_nominatim_service.py tests the
requests to Nominatim.
"""
import pytest

from breedgraph import config
from breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus
from breedgraph.service_layer.infrastructure.geocoding import AbstractGeocodingService, Place

from tests.breedgraph.e2e.utils import post_as, get_verified_payload, assert_payload_success
from tests.breedgraph.scenarios.account_builder import AccountBuilder

GALWAY = Place(name='Galway, Ireland', latitude=53.27, longitude=-9.05, bounds=[[53.2, -9.1], [53.3, -9.0]])
SEARCH = (
    "query ($query: String!, $viewbox: [Float!], $bounded: Boolean, $countryCode: String) { "
    " locationsSearchPlaces(query: $query, viewbox: $viewbox, bounded: $bounded, countryCode: $countryCode) { "
    "  status result { name latitude longitude bounds } errors { name message } } }"
)
COUNTRY = "query ($name: String!) { locationsGeocodeCountry(name: $name) { status result { name latitude longitude } errors { name message } } }"


class FakeGeocoding(AbstractGeocodingService):
    def __init__(self):
        self.searches = []

    async def search_places(self, query, viewbox=None, bounded=False, country_code=None, limit=5):
        self.searches.append((query, viewbox, bounded, country_code, limit))
        return [GALWAY]

    async def geocode_country(self, name):
        self.searches.append((name,))
        return GALWAY if name == 'Ireland' else None


@pytest.fixture
def geocoding(test_app, monkeypatch):
    fake = FakeGeocoding()
    monkeypatch.setattr(test_app, 'geocoding_service', fake)
    return fake


@pytest.mark.asyncio(loop_scope="session")
async def test_search_places(client, login_token_factory, uow_factory, geocoding):
    user_id = await AccountBuilder(uow_factory).account()
    payload = get_verified_payload(await post_as(client, login_token_factory, user_id, SEARCH, {
        'query': 'Galway', 'viewbox': [-10, 53, -8, 54], 'bounded': True, 'countryCode': 'IE'
    }), 'locationsSearchPlaces')
    assert_payload_success(payload)
    assert payload['result'] == [
        {'name': 'Galway, Ireland', 'latitude': 53.27, 'longitude': -9.05, 'bounds': [[53.2, -9.1], [53.3, -9.0]]}
    ]
    assert geocoding.searches == [('Galway', [-10, 53, -8, 54], True, 'IE', 5)]

    payload = get_verified_payload(await post_as(client, login_token_factory, user_id, COUNTRY, {'name': 'Ireland'}), 'locationsGeocodeCountry')
    assert payload['result']['name'] == 'Galway, Ireland'
    payload = get_verified_payload(await post_as(client, login_token_factory, user_id, COUNTRY, {'name': 'Nowhere'}), 'locationsGeocodeCountry')
    assert payload['status'] == GQLStatus.SUCCESS.name and payload['result'] is None


@pytest.mark.asyncio(loop_scope="session")
async def test_searches_need_an_account(client, login_token_factory, geocoding):
    payload = get_verified_payload(await post_as(client, login_token_factory, None, SEARCH, {'query': 'Galway'}), 'locationsSearchPlaces')
    assert payload['status'] != GQLStatus.SUCCESS.name
    assert geocoding.searches == []


@pytest.mark.asyncio(loop_scope="session")
async def test_searches_are_limited_per_hour(client, login_token_factory, uow_factory, geocoding, monkeypatch):
    monkeypatch.setattr(config, 'GEOCODING_RATE_LIMIT_PER_HOUR', 2)
    user_id = await AccountBuilder(uow_factory).account()
    statuses = [
        get_verified_payload(await post_as(client, login_token_factory, user_id, SEARCH, {'query': 'Galway'}), 'locationsSearchPlaces')
        for _ in range(3)
    ]
    assert [payload['status'] for payload in statuses[:2]] == [GQLStatus.SUCCESS.name] * 2
    assert statuses[2]['status'] == GQLStatus.ERROR.name
    assert 'limit of place searches' in statuses[2]['errors'][0]['message']
    assert len(geocoding.searches) == 2
