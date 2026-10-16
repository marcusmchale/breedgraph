"""
A dry run of the BreedCAFS migration on the extracted and curated data, against the test database.
It takes a while, so runs only with BREEDCAFS_DRY_RUN=1.
Only the input files of the data directory are copied (bundle.INPUT_FILES), as the server gets them: mapping files
left by an earlier run would be resumed from, and the files written by this run don't replace those in the data directory.
"""
import csv
import os
import shutil
import time

import pytest

from breedgraph.domain.model.accounts import OntologyRole

from breedgraph.service_layer.infrastructure import archival_service

from breedcafs_migration import ontology, germplasm, locations, layouts, units, programs, datasets, curves, persons, validate
from breedcafs_migration.bootstrap import MigrationContext
from breedcafs_migration.bundle import INPUT_FILES
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
    data_dir.mkdir()
    for name in INPUT_FILES:
        shutil.copyfile(BREEDCAFS_DATA_DIR / name, data_dir / name)
    for module in (ontology, germplasm, locations, layouts, units, programs, datasets, curves, persons, validate):
        monkeypatch.setattr(module, 'BREEDCAFS_DATA_DIR', data_dir)
    monkeypatch.setattr(archival_service, 'FILE_STORAGE_PATH', str(tmp_path / 'files'))

    account = await AccountBuilder(uow_factory=uow_factory).account_with_affiliations(ontology_role=OntologyRole.EDITOR)
    # Persons require the organisation to have declared its legal entity, as the bootstrap checks
    async with uow_factory.get_uow(user_id=account['user_id']) as uow:
        organisation = await uow.repositories.organisations.get(team_id=account['team_id'])
        organisation.declare_legal_entity(
            agent_id=account['user_id'], team_id=account['team_id'], legal_name="University",
            privacy_contact="dataprotection@example.org", terms_version="test", current_terms_version="test"
        )
        await uow.commit()
    started = time.monotonic()
    context = MigrationContext(user_id=account['user_id'], team_id=account['team_id'])
    await migrate(uow_factory, context)
    print(f"\nMigration took {time.monotonic() - started:.0f} s")

    validation = await validate.validate_breedcafs_migration(uow_factory, context)
    print((data_dir / 'validation_report.md').read_text())
    assert validation.passed, [(check.name, check.detail) for check in validation.checks if not check.passed]

    with open(data_dir / 'unit_ids.csv') as f:
        unit_ids = {row['item_uid']: row['unit_id'] for row in csv.DictReader(f)}
    with open(data_dir / 'skipped_items.csv') as f:
        skipped = {row['item_uid'] for row in csv.DictReader(f)}
    with open(data_dir / 'item_name_subject_sources_sinks.csv', encoding='utf-8-sig') as f:
        items = {row['item_uid'].strip('"') for row in csv.DictReader(f)}
    with open(data_dir / 'factor_records.csv') as f:
        treatment_trees = {row['item_uid'] for row in csv.DictReader(f)}
    # Every item is a unit, except skipped items, duplicates, blocks, branches, leaves and the samples left out
    skipped |= set(units.DUPLICATE_ITEMS)
    plan = units.UnitPlan(units.read_items())
    not_units = set(plan.treatment_blocks) | set(plan.design_blocks) | set(plan.coded) | set(plan.left_out)
    assert items - skipped - set(unit_ids) == not_units
    assert (len(plan.treatment_blocks), len(plan.design_blocks), len(plan.left_out)) == (12, 96, 563)
    assert treatment_trees <= set(unit_ids)
    assert len(set(unit_ids.values())) == len(unit_ids)

    with open(data_dir / 'dataset_ids.csv') as f:
        dataset_ids = [row['dataset_id'] for row in csv.DictReader(f)]
    assert len(dataset_ids) == len(set(dataset_ids)) == 1172

    with open(data_dir / 'curve_ids.csv') as f:
        curve_rows = list(csv.DictReader(f))
    assert len({row['dataset_id'] for row in curve_rows}) == len({row['reference_id'] for row in curve_rows}) == 4

    with open(data_dir / 'person_ids.csv') as f:
        person_ids = [row['person_id'] for row in csv.DictReader(f)]
    with open(data_dir / 'persons.csv') as f:
        assert len(person_ids) == len(set(person_ids)) == len(list(csv.DictReader(f)))
