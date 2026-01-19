import pytest, pytest_asyncio


import logging
logger = logging.getLogger(__name__)


@pytest.mark.usefixtures("session_database")
@pytest.mark.asyncio(scope="session")
async def test_get_dataset_summaries(bus, uncommitted_neo4j_tx, first_unstored_account, study_with_dataset):
    await uncommitted_neo4j_tx.commit()
    async with bus.views.get_views(user_id=first_unstored_account.user.id) as views:
        summaries = await views.datasets.get_dataset_summaries(study_id=study_with_dataset.id)
        assert summaries, f"Expected dataset summaries for study {study_with_dataset.id}, but got none"


