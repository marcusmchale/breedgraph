# BreedCAFS Migration Runbook

The steps to run the migration on a BreedGraph database, the README's phases in order.
The migration is run on a fresh copy of the production database: after the initial setup and the germplasm import,
and before other users have access. Run through it locally first, then on the server.

Run from a source checkout (`pip install -e .`), as the migration package is not in the wheel.
Everything below is run from the repository root.

## 1. Before you start

1. **A backup.** Take a dump of the database (`scripts/backup.sh`) and check it restores (`scripts/restore.sh`),
   so a failed run can be rolled back.
2. **The data directory.** Copy `src/data/breedcafs_migration/` (the extracted and curated CSVs; not in git) to the machine,
   and point `BREEDCAFS_DATA_DIR` at it if it is elsewhere. It holds Person data: keep it off shared storage,
   and delete any mapping files (`*_ids.csv`, `factor_records.csv`) left from a run on another database,
   since the phases read them back as already created.
3. **The services.** Neo4j and Redis running, with the env files loaded:
   ```bash
   set -a; . instance/breedgraph.env; . instance/private.breedgraph.env; set +a
   ```
   `FILE_STORAGE_PATH` must be the API's file store, where the curve data files are written.
4. **The initial data.** `scripts/setup_initial_data.py` has run (the ontology base, including the Country location type),
   your account exists, and `scripts/import_germplasm.py` has loaded the production germplasm,
   so BreedCAFS varieties are matched to it rather than created again.
5. **Record group types have an extent.** Since record group types gained a required `extent` (SHARED or WITHIN_UNIT),
   one stored without it can't be read, and the ontology phase fails on it. In a copy of production older than that change,
   list any without one, and set each from what its codes mean (README §2.4):
   ```cypher
   MATCH (t:RecordGroupType) WHERE t.extent IS NULL RETURN t.id, t.name, t.description;
   MATCH (t:RecordGroupType {id: <id>}) SET t.extent = 'WITHIN_UNIT';   // or 'SHARED'
   ```
   The migration reuses an existing type named Replicate only if it is WITHIN_UNIT, and stops otherwise.
6. **The University of Galway.** Its root team exists, with its legal entity declared (the data controller of the Persons),
   and your account is an admin of it through a heritable affiliation.

## 2. Bootstrap

```bash
export BREEDCAFS_ADMIN_USER_ID=<your user id>
export BREEDCAFS_PARENT_TEAM_ID=<the University of Galway root team id>
.venv/bin/python -m breedcafs_migration.main bootstrap
```

It creates (or finds) the BreedCAFS Migration user and team, and prints their ids. Note them for the next steps.
It exits with an error saying what to set if a setting is missing or the parent team has no legal entity.

## 3. Migrate

```bash
.venv/bin/python -m breedcafs_migration.main migrate --user-id <migration user id> --team-id <migration team id> \
  2>&1 | tee migration.log
```

The phases run in order: ontology, germplasm, locations, layouts, units, program, datasets, curves, Persons.
Each writes its mapping file to the data directory as it goes. The run takes about 20–25 minutes on a laptop.
Expected, from the dry run:

| Phase | Result |
|---|---|
| Ontology | 103 inputs mapped |
| Germplasm | 112 varieties |
| Locations | 41 fields |
| Layouts | 36 |
| Units | 99,739 |
| Program | 8 studies |
| Datasets | 1,175 with 265,651 records; 1,080 repeated records left out |
| Curves | 4 datasets with 5,084 curves; 16 repeated curves left out |
| Persons | 17, as in persons.csv |

The validation (step 4) checks these against the extracted files, so they need not be compared by hand.

**If it fails**, fix the cause and run the same command again. Every phase matches what it created before
(by name, by the `BreedCAFS item <uid>` unit description, or through its mapping file), so it carries on
from where it stopped. Exit code 2 is a settings or germplasm name conflict, printed as `Error:`;
exit code 1 is anything else, with the traceback in the log.

## 4. After the run

The locations phase has already refreshed the countries in the state store, so the API sees them as stored.

1. **Validate:**
   ```bash
   .venv/bin/python -m breedcafs_migration.main validate --user-id <migration user id> --team-id <migration team id>
   ```
   It only reads, writes `validation_report.md` to the data directory and exits with 3 if a check fails (README §8).
   Resolve failures before going on.
2. **Archive the curve files.** Their archival records are pending; the archive worker archives them once it runs.
3. **Take a backup** of the migrated database.
4. **Keep the artefacts** (README §13): the data directory with its mapping files and validation report, and the log,
   somewhere private, as they hold Person data.

Everything stays `PRIVATE` under the migration team until handover (README §9–10),
which follows the DPO's review of the privacy notice and data processing terms.
