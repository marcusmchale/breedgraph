import httpx
import pytest

from breedgraph import config
from breedgraph.adapters.nominatim import geocoding_service as nominatim_module
from breedgraph.adapters.nominatim import NominatimGeocodingService
from breedgraph.custom_exceptions import IllegalOperationError
from breedgraph.service_layer.infrastructure.geocoding import Place

REAL_CLIENT = httpx.AsyncClient
RESULT = {'display_name': 'Galway, Ireland', 'lat': '53.27', 'lon': '-9.05', 'boundingbox': ['53.2', '53.3', '-9.1', '-9.0']}


@pytest.fixture(autouse=True)
def settings(monkeypatch):
    monkeypatch.setattr(config, 'NOMINATIM_URL', 'https://nominatim.test')
    monkeypatch.setattr(config, 'MAIL_FROM', 'breedgraph@example.org')


def mock_nominatim(monkeypatch, status: int, body, requests: list):
    def handle(request: httpx.Request):
        requests.append(request)
        return httpx.Response(status, json=body)
    monkeypatch.setattr(nominatim_module.httpx, 'AsyncClient', lambda **kwargs: REAL_CLIENT(transport=httpx.MockTransport(handle)))


@pytest.mark.asyncio
async def test_search_places(monkeypatch):
    requests = []
    mock_nominatim(monkeypatch, 200, [RESULT], requests)
    places = await NominatimGeocodingService().search_places(
        ' Galway ', viewbox=[-10.0, 53.0, -8.0, 54.0], bounded=True, country_code='IE', limit=3
    )
    assert places == [Place(name='Galway, Ireland', latitude=53.27, longitude=-9.05, bounds=[[53.2, -9.1], [53.3, -9.0]])]
    [request] = requests
    assert request.url.host == 'nominatim.test' and request.url.path == '/search'
    assert dict(request.url.params) == {
        'q': 'Galway', 'limit': '3', 'viewbox': '-10.0,53.0,-8.0,54.0', 'bounded': '1', 'countrycodes': 'ie',
        'format': 'json'
    }
    # the application and a contact, as Nominatim's usage policy asks; nothing about the user
    assert request.headers['User-Agent'] == 'BreedGraph (breedgraph@example.org)'


@pytest.mark.asyncio
async def test_geocode_country(monkeypatch):
    requests = []
    mock_nominatim(monkeypatch, 200, [{**RESULT, 'boundingbox': None}], requests)
    place = await NominatimGeocodingService().geocode_country('Ireland')
    assert place.latitude == 53.27 and place.bounds is None
    assert dict(requests[0].url.params) == {'country': 'Ireland', 'limit': '1', 'format': 'json'}
    mock_nominatim(monkeypatch, 200, [], requests)
    assert await NominatimGeocodingService().geocode_country('Nowhere') is None


@pytest.mark.asyncio
async def test_empty_searches_ask_nothing(monkeypatch):
    requests = []
    mock_nominatim(monkeypatch, 200, [RESULT], requests)
    assert await NominatimGeocodingService().search_places('  ') == []
    assert await NominatimGeocodingService().geocode_country('') is None
    assert requests == []


@pytest.mark.asyncio
async def test_failures(monkeypatch):
    mock_nominatim(monkeypatch, 503, {}, [])
    with pytest.raises(IllegalOperationError, match="not available"):
        await NominatimGeocodingService().search_places('Galway')
