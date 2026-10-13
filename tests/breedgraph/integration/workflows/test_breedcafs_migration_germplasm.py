import csv
import shutil

import pytest
import pytest_asyncio

from breedgraph.domain.model.controls import ReadRelease
from breedgraph.domain.model.germplasm import GermplasmInput, GermplasmSourceType

from breedcafs_migration import germplasm
from breedcafs_migration.bootstrap import MigrationContext
from breedcafs_migration.germplasm import prepare_breedcafs_germplasm, GermplasmNameConflict, BREEDCAFS_VARIETIES, read_varieties
from breedcafs_migration.setup.config import BREEDCAFS_DATA_DIR

from tests.breedgraph.scenarios.account_builder import AccountBuilder


async def create_entry(uow_factory, account: dict, entry: GermplasmInput, release: ReadRelease) -> int:
    async with uow_factory.get_uow(user_id=account['user_id'], write_team=account['team_id'], release=release) as uow:
        stored = await uow.germplasm.create_entry(entry)
        await uow.commit()
        return stored.id


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def germplasm_context(isolated_state, uow_factory) -> dict:
    account_builder = AccountBuilder(uow_factory=uow_factory)
    migration = await account_builder.account_with_affiliations()
    curators = await account_builder.account_with_affiliations()
    registered_id = await create_entry(
        uow_factory, curators, GermplasmInput(name="Marsellesa", synonyms=["Sarchimor T5296"]), ReadRelease.REGISTERED
    )
    await create_entry(uow_factory, curators, GermplasmInput(name="Private Variety"), ReadRelease.PRIVATE)
    return {
        'context': MigrationContext(user_id=migration['user_id'], team_id=migration['team_id']),
        'registered_id': registered_id
    }


def data_dir(tmp_path, monkeypatch, varieties: list[str]):
    with open(tmp_path / 'varieties.csv', 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['v.name'])
        writer.writerows([[f'"{name}"'] for name in varieties])
    monkeypatch.setattr(germplasm, 'BREEDCAFS_DATA_DIR', tmp_path)
    return tmp_path


@pytest.mark.asyncio(loop_scope="session")
async def test_unreadable_names_are_reported(uow_factory, germplasm_context, tmp_path, monkeypatch):
    data_dir(tmp_path, monkeypatch, ["Marsellesa", "private  variety"])
    with pytest.raises(GermplasmNameConflict, match="private  variety"):
        await prepare_breedcafs_germplasm(uow_factory, germplasm_context['context'])


@pytest.mark.asyncio(loop_scope="session")
async def test_prepare_germplasm(uow_factory, germplasm_context, tmp_path, monkeypatch):
    context = germplasm_context['context']
    directory = data_dir(tmp_path, monkeypatch, [
        "Marsellesa", "sarchimor  t5296", "Starmaya / Nemaya", "Starmaya", "Nemaya", "Catimor 129",
        "ET26 A1", "Marsellesa x ET26A1", "Catimor 129 X ET1"
    ])

    ids = await prepare_breedcafs_germplasm(uow_factory, context)

    assert ids.varieties["Marsellesa"] == germplasm_context['registered_id']
    assert ids.varieties["sarchimor  t5296"] == germplasm_context['registered_id']
    assert ids.created_from_breedcafs == {
        "Starmaya / Nemaya", "Starmaya", "Nemaya", "Catimor 129", "ET26 A1", "Marsellesa x ET26A1", "Catimor 129 X ET1"
    }
    assert ids.parents_created == {"ET1"}
    # BreedCAFS Varieties, 4 varieties, 2 crosses, 1 graft and the missing parent
    assert ids.created == 9

    async with uow_factory.get_uow(user_id=context.user_id) as uow:
        group = await uow.germplasm.get_entry(ids.varieties_id)
        assert group.name == BREEDCAFS_VARIETIES
        for name in ids.created_from_breedcafs:
            controller = await uow.controls.get_controller(group.label, ids.varieties[name])
            assert controller.release is ReadRelease.PRIVATE
            assert set(controller.controls) == {context.team_id}
        for name in ids.created_from_breedcafs - {"Starmaya / Nemaya", "Marsellesa x ET26A1", "Catimor 129 X ET1"}:
            sources = [r.source_id async for r in uow.germplasm.get_source_relationships(ids.varieties[name])]
            assert sources == [ids.varieties_id]
        graft_sources = {
            (r.source_id, r.source_type, r.description)
            async for r in uow.germplasm.get_source_relationships(ids.varieties["Starmaya / Nemaya"])
        }
        assert graft_sources == {
            (ids.varieties["Starmaya"], GermplasmSourceType.TISSUE, "Scion"),
            (ids.varieties["Nemaya"], GermplasmSourceType.TISSUE, "Rootstock"),
        }

        async def parents(name: str) -> set:
            return {(r.source_id, r.source_type) async for r in uow.germplasm.get_source_relationships(ids.varieties[name])}

        assert await parents("Marsellesa x ET26A1") == {
            (germplasm_context['registered_id'], GermplasmSourceType.MATERNAL),
            (ids.varieties["ET26 A1"], GermplasmSourceType.PATERNAL),
        }
        et1 = [entry async for entry in uow.germplasm.get_entries(names=["ET1"])]
        assert len(et1) == 1
        assert await parents("Catimor 129 X ET1") == {
            (ids.varieties["Catimor 129"], GermplasmSourceType.MATERNAL),
            (et1[0].id, GermplasmSourceType.PATERNAL),
        }
        assert {r.source_id async for r in uow.germplasm.get_source_relationships(et1[0].id)} == {ids.varieties_id}

    with open(directory / 'germplasm_ids.csv') as f:
        rows = {row['variety']: row for row in csv.DictReader(f)}
    assert rows["Marsellesa"]['source'] == 'existing'
    assert rows["Catimor 129"]['source'] == 'breedcafs'

    again = await prepare_breedcafs_germplasm(uow_factory, context)
    assert again.created == 0
    assert again.varieties == ids.varieties
    assert again.created_from_breedcafs == ids.created_from_breedcafs


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.skipif(
    not (BREEDCAFS_DATA_DIR / 'varieties.csv').exists(),
    reason="The BreedCAFS varieties are not in the data directory"
)
async def test_prepare_germplasm_from_extracted_varieties(uow_factory, germplasm_context, tmp_path, monkeypatch):
    shutil.copy(BREEDCAFS_DATA_DIR / 'varieties.csv', tmp_path / 'varieties.csv')
    monkeypatch.setattr(germplasm, 'BREEDCAFS_DATA_DIR', tmp_path)

    ids = await prepare_breedcafs_germplasm(uow_factory, germplasm_context['context'])
    assert set(ids.varieties) == set(read_varieties())
    assert len(ids.parents_created) == 8
