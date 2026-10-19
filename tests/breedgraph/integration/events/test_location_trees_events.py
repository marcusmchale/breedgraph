import pytest

from breedgraph.config import get_vue_url
from breedgraph.domain.events.location_trees import MapRegionFetching, MapCountryDivided, MapRegionReady, MapRegionFailed
from breedgraph.service_layer.handlers.events.location_trees import (
    notify_map_region_fetching, notify_map_country_divided, notify_map_region_ready, notify_map_region_failed
)

from tests.breedgraph.scenarios.account_builder import AccountBuilder


class RecordingNotifications:
    def __init__(self):
        self.sent = []

    async def send(self, recipients, message):
        self.sent.append((recipients, message))


@pytest.mark.asyncio(loop_scope="session")
async def test_map_regions_email_their_requestors(uow_factory, isolated_state):
    user_ids = [await AccountBuilder(uow_factory).account(), await AccountBuilder(uow_factory).account()]
    notifications = RecordingNotifications()
    for handler, event in (
            (notify_map_region_fetching, MapRegionFetching),
            (notify_map_country_divided, MapCountryDivided),
            (notify_map_region_ready, MapRegionReady),
            (notify_map_region_failed, MapRegionFailed)
    ):
        # an account deleted since is skipped
        await handler(
            event(name='Luxembourg', user_ids=[*user_ids, 9999]), uow_factory=uow_factory, notifications=notifications
        )

    assert [sorted(user.id for user in recipients) for recipients, _ in notifications.sent] == [user_ids] * 4
    subjects = [message.message['Subject'] for _, message in notifications.sent]
    bodies = [message.message.get_content() for _, message in notifications.sent]
    assert subjects[0].endswith('fetching detailed maps for Luxembourg')
    assert "we'll email you when they're ready" in bodies[0]
    assert 'Luxembourg is too large to fetch whole' in bodies[1]
    assert f'{get_vue_url()}locations' in bodies[2]
    assert subjects[3].endswith('detailed maps for Luxembourg could not be fetched')

    # no one to tell, no email
    await notify_map_region_ready(MapRegionReady(name='Luxembourg', user_ids=[9999]), uow_factory=uow_factory, notifications=notifications)
    assert len(notifications.sent) == 4
