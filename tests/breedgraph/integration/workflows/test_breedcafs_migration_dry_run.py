"""
A dry run of the BreedCAFS migration on the extracted and curated data, against the test database.
It takes a while, so runs only with BREEDCAFS_DRY_RUN=1.
The data directory is copied, so the mapping files written by the run do not replace those in the data directory.
"""
import csv
import os
import shutil
import time

import pytest

from breedgraph.domain.model.accounts import OntologyRole

from breedcafs_migration import ontology, germplasm, locations, layouts, units
from breedcafs_migration.bootstrap import MigrationContext
from breedcafs_migration.main import migrate
from breedcafs_migration.setup.config import BREEDCAFS_DATA_DIR

from tests.breedgraph.scenarios.account_builder import AccountBuilder

pytestmark = pytest.mark.skipif(
    os.getenv('BREEDCAFS_DRY_RUN') != '1' or not BREEDCAFS_DATA_DIR.exists(),
    reason="Set BREEDCAFS_DRY_RUN=1 to run the migration on the data in the data directory"
)


@pytest.mark.asyncio(loop_scope="session")
async def test_dry_run(uow_factory, isolated_state, tmp_path, monkeypatch):
    data_dir = tmp_path / 'data'
    shutil.copytree(BREEDCAFS_DATA_DIR, data_dir)
    for module in (ontology, germplasm, locations, layouts, units):
        monkeypatch.setattr(module, 'BREEDCAFS_DATA_DIR', data_dir)

    account = await AccountBuilder(uow_factory=uow_factory).account_with_affiliations(ontology_role=OntologyRole.EDITOR)
    started = time.monotonic()
    await migrate(uow_factory, MigrationContext(user_id=account['user_id'], team_id=account['team_id']))
    print(f"\nMigration took {time.monotonic() - started:.0f} s")

    with open(data_dir / 'unit_ids.csv') as f:
        unit_ids = {row['item_uid']: row['unit_id'] for row in csv.DictReader(f)}
    with open(data_dir / 'skipped_items.csv') as f:
        skipped = {row['item_uid'] for row in csv.DictReader(f)}
    with open(data_dir / 'item_name_subject_sources_sinks.csv', encoding='utf-8-sig') as f:
        items = {row['item_uid'].strip('"') for row in csv.DictReader(f)}
    with open(data_dir / 'factor_records.csv') as f:
        treatment_trees = {row['item_uid'] for row in csv.DictReader(f) if row['factor'] != 'Stratum'}
    # Every item is a unit, except skipped items and the blocks named after a treatment
    treatment_blocks = {uid for uid in items - skipped - set(unit_ids) if '_B' in uid}
    assert items - skipped - set(unit_ids) == treatment_blocks
    assert len(treatment_blocks) == 12
    assert treatment_trees <= set(unit_ids)
    assert len(set(unit_ids.values())) == len(unit_ids)
