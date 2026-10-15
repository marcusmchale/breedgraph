import pytest
import pytest_asyncio

from breedgraph.domain.model.controls import ControlledModelLabel, ReadRelease
from breedgraph.domain.model.germplasm import GermplasmInput

from breedcafs_migration.writes import consolidate_write_stamps, models_with_extra_stamps
from tests.breedgraph.scenarios.account_builder import AccountBuilder


async def entry_written_three_times(uow_factory, account: dict, name: str) -> int:
    """A germplasm entry created, then updated in two more transactions: three write stamps"""
    async with uow_factory.get_uow(user_id=account['user_id'], write_team=account['team_id'], release=ReadRelease.PRIVATE) as uow:
        entry = await uow.germplasm.create_entry(GermplasmInput(name=name))
        await uow.commit()
    for description in ("first", "second"):
        async with uow_factory.get_uow(user_id=account['user_id']) as uow:
            stored = await uow.germplasm.get_entry(entry.id)
            stored.description = description
            await uow.germplasm.update_entry(stored)
            await uow.commit()
    return entry.id


async def writes(uow_factory, user_id: int, entry_id: int):
    async with uow_factory.get_uow(user_id=user_id) as uow:
        return (await uow.controls.get_controller(ControlledModelLabel.GERMPLASM, entry_id)).writes


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def written(isolated_state, uow_factory) -> dict:
    builder = AccountBuilder(uow_factory=uow_factory)
    migration, other = await builder.account_with_affiliations(), await builder.account_with_affiliations()
    return {
        'migration': migration,
        'other': other,
        'migrated': await entry_written_three_times(uow_factory, migration, "Migrated variety"),
        'others': await entry_written_three_times(uow_factory, other, "Other variety"),
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_consolidate_keeps_the_earliest_migration_stamp(uow_factory, written):
    migration_id = written['migration']['user_id']
    before = await writes(uow_factory, migration_id, written['migrated'])
    assert len(before) == 3
    assert (await models_with_extra_stamps(uow_factory, migration_id))[ControlledModelLabel.GERMPLASM] == 1

    assert await consolidate_write_stamps(uow_factory, migration_id) == 2

    after = await writes(uow_factory, migration_id, written['migrated'])
    assert after == before[:1]
    assert (await models_with_extra_stamps(uow_factory, migration_id))[ControlledModelLabel.GERMPLASM] == 0
    # other users' stamps are kept
    assert len(await writes(uow_factory, written['other']['user_id'], written['others'])) == 3
    # and running it again changes nothing
    assert await consolidate_write_stamps(uow_factory, migration_id) == 0
