"""
Place searches for the location map, answered by the API from its copy of GeoNames' places (adapters/geonames), so
no search leaves the server, and open to visitors. Here the places are the few in tests/map_worker/geonames_fixtures.py,
loaded into a gazetteer of the test's own; tests/breedgraph/integration/services/test_gazetteer.py tests their fetching.
"""
import pytest
import pytest_asyncio

from breedgraph.adapters.geonames import GeoNamesGazetteer
from breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus
from map_worker.fetching import write_gazetteer, read_shapes
from tests.breedgraph.e2e.utils import post_as, get_verified_payload, assert_payload_success
from tests.breedgraph.scenarios.account_builder import AccountBuilder
from tests.breedgraph.unit.adapters.test_gazetteer_index import zipped, EXTRA_IRISH
from tests.map_worker.geonames_fixtures import IRELAND, ADMIN1, ADMIN2, FEATURES, write_site

SEARCH = (
    "query ($query: String!, $viewbox: [Float!], $bounded: Boolean, $country: String) { "
    " locationsSearchPlaces(query: $query, viewbox: $viewbox, bounded: $bounded, country: $country) { "
    "  status result { name latitude longitude bounds description region country countryCode zoom } errors { name message } } }"
)
COUNTRY = "query ($code: String!) { locationsCountryPlace(code: $code) { status result { name bounds description } errors { name message } } }"
STATUS = "query { locationsMapStatus(code: \"IRL\") { status result { places { state enabled towns error } } errors { name message } } }"


@pytest_asyncio.fixture(loop_scope="session")
async def gazetteer(bus, state_store, tmp_path, monkeypatch) -> GeoNamesGazetteer:
    """The world's towns and Ireland's places, loaded as the map worker's files would be, in place of the app's"""
    site = write_site(tmp_path / 'site')
    world, ireland = tmp_path / 'world.tsv.gz', tmp_path / 'IRL.tsv.gz'
    write_gazetteer(site / 'cities1000.zip', 'cities1000.txt', world, None, ADMIN1, ADMIN2, FEATURES,
                    read_shapes(site / 'shapes_simplified_low.json.zip'))
    write_gazetteer(zipped(tmp_path / 'IE.zip', 'IE.txt', IRELAND + EXTRA_IRISH), 'IE.txt', ireland, 'IE', ADMIN1,
                    ADMIN2, FEATURES)
    gazetteer = GeoNamesGazetteer(state_store, path=tmp_path / 'gazetteer', worker=False, geonames_url='')
    await gazetteer.start()
    gazetteer.index.load_world(world)
    gazetteer.index.load_country('IRL', ireland)
    monkeypatch.setattr(bus, 'gazetteer', gazetteer)
    yield gazetteer
    await gazetteer.stop()


async def search(client, login_token_factory, user_id=None, **variables) -> dict:
    return get_verified_payload(
        await post_as(client, login_token_factory, user_id, SEARCH, variables), 'locationsSearchPlaces'
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_visitors_find_places_with_their_kind_and_region(client, login_token_factory, gazetteer):
    payload = await search(client, login_token_factory, query='ballyduff kerry')
    assert_payload_success(payload)
    assert payload['result'] == [{
        'name': 'Ballyduff', 'latitude': 52.45593, 'longitude': -9.66399, 'bounds': None, 'description': 'village',
        'region': 'Kerry, Munster', 'country': 'Ireland', 'countryCode': 'IRL', 'zoom': 14
    }]
    farm = (await search(client, login_token_factory, query='Oak Park'))['result'][0]
    assert (farm['description'], farm['zoom']) == ('farm', 16)
    ireland = (await search(client, login_token_factory, query='Éire'))['result'][0]
    assert (ireland['name'], ireland['bounds'], ireland['country']) == ('Ireland', [[51.4, -10.5], [55.4, -6.0]], None)


@pytest.mark.asyncio(loop_scope="session")
async def test_signed_in_users_find_them_too(client, login_token_factory, uow_factory, gazetteer):
    user_id = await AccountBuilder(uow_factory).account()
    payload = await search(client, login_token_factory, user_id, query='Gaillimh')
    assert [place['name'] for place in payload['result']] == ['Galway']


@pytest.mark.asyncio(loop_scope="session")
async def test_a_search_is_bounded_by_a_country_or_the_maps_view(client, login_token_factory, gazetteer):
    assert (await search(client, login_token_factory, query='galway', country='IRN'))['result'] == []
    assert [p['name'] for p in (await search(client, login_token_factory, query='qazvin', country='IRN'))['result']] \
        == ['Qazvin']
    waterford = [-7.5, 52.0, -7.0, 52.5]
    found = (await search(client, login_token_factory, query='ballyduff', viewbox=waterford, bounded=True))['result']
    assert [p['region'] for p in found] == ['County Waterford, Munster']

    refused = await search(client, login_token_factory, query='galway', country='IE')
    assert refused['status'] == GQLStatus.ERROR.name
    assert refused['errors'][0]['message'] == "Not an ISO 3166 alpha-3 code: 'IE'"
    refused = await search(client, login_token_factory, query='galway', viewbox=[1, 2, 3])
    assert refused['errors'][0]['message'] == 'A viewbox is [west, south, east, north]'


@pytest.mark.asyncio(loop_scope="session")
async def test_at_most_five_searches_are_made_in_a_request(client, login_token_factory, gazetteer):
    query = 'query { ' + ' '.join(
        f'q{i}: locationsSearchPlaces(query: "galway") {{ status errors {{ message }} }}' for i in range(6)
    ) + ' }'
    data = (await post_as(client, login_token_factory, None, query)).json()['data']
    statuses = [data[f'q{i}']['status'] for i in range(6)]
    assert statuses.count(GQLStatus.SUCCESS.name) == 5 and statuses.count(GQLStatus.ERROR.name) == 1


@pytest.mark.asyncio(loop_scope="session")
async def test_a_country_is_found_by_its_code_and_its_places_status_shown(client, login_token_factory, gazetteer):
    payload = get_verified_payload(await post_as(client, login_token_factory, None, COUNTRY, {'code': 'FJI'}), 'locationsCountryPlace')
    assert payload['result'] == {'name': 'Fiji', 'bounds': [[-19.0, 177.0], [-16.0, 181.5]], 'description': 'country'}
    payload = get_verified_payload(await post_as(client, login_token_factory, None, COUNTRY, {'code': 'FRA'}), 'locationsCountryPlace')
    assert (payload['status'], payload['result']) == (GQLStatus.SUCCESS.name, None), 'GeoNames gave no shape'
    payload = get_verified_payload(await post_as(client, login_token_factory, None, COUNTRY, {'code': 'Ireland'}), 'locationsCountryPlace')
    assert payload['status'] == GQLStatus.ERROR.name

    payload = get_verified_payload(await post_as(client, login_token_factory, None, STATUS), 'locationsMapStatus')
    assert payload['result']['places'] == {'state': 'READY', 'enabled': False, 'towns': True, 'error': None}
