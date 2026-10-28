"""
Where a country's detailed maps stand (locationsMapStatus), which BreedView's location map shows under the map: open
to visitors, as the map files are. The map regions service here is a fake on the bus;
tests/breedgraph/integration/services/test_map_regions.py tests the status it gives.
"""
import pytest

from breedgraph.entrypoints.fastapi.graphql.decorators import GQLStatus
from breedgraph.service_layer.infrastructure.map_regions import (
    AbstractMapRegions, CountryMapStatus, MapSectionStatus, MapState
)

from tests.breedgraph.e2e.utils import post_as, get_verified_payload, assert_payload_success

STATUS = (
    "query ($code: String!) { locationsMapStatus(code: $code) { status "
    " result { code state size limit enabled error sections { name state size error } } errors { name message } } }"
)


class FakeMapRegions(AbstractMapRegions):
    async def start(self):
        pass

    async def stop(self):
        pass

    async def request_country(self, code):
        pass

    async def request_places(self, code, coordinates):
        pass

    async def remove_country(self, code):
        pass

    async def status(self, code):
        return CountryMapStatus(code, MapState.DIVIDED, 2 * 10 ** 9, True, 17 * 10 ** 9, sections=[
            MapSectionStatus('Alpha', MapState.READY, 10 ** 9),
            MapSectionStatus('Beta Two', MapState.FAILED, 25 * 10 ** 8, "they would take 2.5 GB, more than ...")
        ])


@pytest.mark.asyncio(loop_scope="session")
async def test_a_countrys_map_status_is_open_to_visitors(client, login_token_factory, test_app, monkeypatch):
    monkeypatch.setattr(test_app.bus, 'map_regions', FakeMapRegions())
    payload = get_verified_payload(await post_as(client, login_token_factory, None, STATUS, {'code': 'USA'}), 'locationsMapStatus')
    assert_payload_success(payload)
    assert payload['result'] == {
        'code': 'USA', 'state': 'DIVIDED', 'size': 17e9, 'limit': 2e9, 'enabled': True, 'error': None, 'sections': [
            {'name': 'Alpha', 'state': 'READY', 'size': 1e9, 'error': None},
            {'name': 'Beta Two', 'state': 'FAILED', 'size': 2.5e9, 'error': "they would take 2.5 GB, more than ..."}
        ]
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_a_site_without_map_regions_fetches_none_and_codes_are_checked(client, login_token_factory, test_app, monkeypatch):
    monkeypatch.setattr(test_app.bus, 'map_regions', None)
    payload = get_verified_payload(await post_as(client, login_token_factory, None, STATUS, {'code': 'LUX'}), 'locationsMapStatus')
    assert (payload['result']['state'], payload['result']['enabled'], payload['result']['sections']) == ('NONE', False, [])

    payload = get_verified_payload(await post_as(client, login_token_factory, None, STATUS, {'code': 'lux'}), 'locationsMapStatus')
    assert payload['status'] == GQLStatus.ERROR.name
    assert payload['errors'][0]['message'] == "Not an ISO 3166 alpha-3 code: 'lux'"
