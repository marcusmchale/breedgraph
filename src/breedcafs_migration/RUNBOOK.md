# BreedCAFS Migration Runbook

The steps to run the migration on a BreedGraph database, the README's phases in order.
The migration is run on a fresh copy of the production database: after the initial setup and the germplasm import,
and before other users have access.

Extraction and loading run in different places. The data is extracted and curated where the legacy BreedCAFS
database is, and rehearsed there (§1). It goes to the server as a checked bundle, with the migration as its own
wheel, and is loaded there (§2–5). The server never needs the legacy database, or a source checkout.

## 1. Locally: extract, rehearse, package

1. **Extract and curate** the data into `src/data/breedcafs_migration/` (README §1; not in git, as it holds Person data).
2. **Rehearse** on the synthetic test database, rebuilt (`scripts/build_test_database.py`) or restored from its dump:
   ```bash
   set -a; . instance/breedgraph.env; . instance/private.breedgraph.env; set +a
   python scripts/rehearse_migration.py --manifest instance/neo4j_archive/test_database.manifest.json 2>&1 | tee rehearsal.log
   ```
   It sets up what §2 expects (a team with a legal entity, the production germplasm), bundles and unbundles the data
   as below, runs §3–4 and the validation, and exits with the validation's status. Dump the result privately if
   you keep it: it holds BreedCAFS and Person data.
3. **Build** the BreedGraph wheelhouse as for any deployment (README), and the migration wheel:
   ```bash
   python scripts/build_migration_wheel.py
   ```
   It holds only the migration's Python files, which the script checks: never the data, notes or extraction docs.
4. **Bundle** the data:
   ```bash
   python -m breedcafs_migration.main bundle --out breedcafs_bundle.tar.gz
   ```
   It packs exactly the 17 input files, with a manifest of their checksums, and none of the files a run writes
   (mappings, curve data files, the validation report). The bundle is readable by you only.
5. **Copy** the migration wheel and the bundle to the server securely (e.g. `scp`), into a private directory,
   off shared storage.

## 2. On the server: before you start

1. **A backup.** Take a dump of the database (`scripts/backup.sh`) and check it restores (`scripts/restore.sh`),
   so a failed run can be rolled back.
2. **The services.** Neo4j and Redis running, with the API's environment loaded, e.g.:
   ```bash
   set -a; . instance/breedgraph.env; . instance/private.breedgraph.env; set +a
   ```
   `FILE_STORAGE_PATH` must be the API's file store, where the curve data files are written.
3. **The initial data.** `scripts/setup_initial_data.py` has run (the ontology base, including the Country location type),
   your account exists, and `scripts/import_germplasm.py` has loaded the production germplasm,
   so BreedCAFS varieties are matched to it rather than created again.
4. **Record group types have an extent.** Since record group types gained a required `extent` (SHARED or WITHIN_UNIT),
   one stored without it can't be read, and the ontology phase fails on it. In a copy of production older than that change,
   list any without one, and set each from what its codes mean (README §2.4):
   ```cypher
   MATCH (t:RecordGroupType) WHERE t.extent IS NULL RETURN t.id, t.name, t.description;
   MATCH (t:RecordGroupType {id: <id>}) SET t.extent = 'WITHIN_UNIT';   // or 'SHARED'
   ```
   The migration reuses an existing type named Replicate only if it is WITHIN_UNIT, and stops otherwise.
5. **The University of Galway.** Its root team exists, with its legal entity declared (the data controller of the Persons),
   and your account is an admin of it through a heritable affiliation.
6. **Install the migration** into the API's environment, without dependencies (BreedGraph is already installed):
   ```bash
   python -m pip install --no-deps breedcafs_migration-<version>-py3-none-any.whl
   ```
7. **Unpack the data** into a new, private directory, and point the migration at it:
   ```bash
   breedcafs-migration unbundle breedcafs_bundle.tar.gz --data-dir <data dir>
   export BREEDCAFS_DATA_DIR=<data dir>
   ```
   Every file is checked against the bundle's manifest first; nothing is unpacked if one is missing or altered.
   The directory must be new, so no mapping files from another run can be read back as already created.

## 3. Bootstrap

```bash
export BREEDCAFS_ADMIN_USER_ID=<your user id>
export BREEDCAFS_PARENT_TEAM_ID=<the University of Galway root team id>
breedcafs-migration bootstrap
```

It creates (or finds) the BreedCAFS Migration user and team, and prints their ids. Note them for the next steps.
It exits with an error saying what to set if a setting is missing or the parent team has no legal entity.

## 4. Migrate

```bash
breedcafs-migration migrate --user-id <migration user id> --team-id <migration team id> 2>&1 | tee migration.log
```

The phases run in order: ontology, germplasm, locations, layouts, units, program, datasets, curves, Persons,
and last the consolidation of the migration's write stamps (README §14).
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

The validation (§5) checks these against the extracted files, so they need not be compared by hand.
The locations phase refreshes the countries in the state store, so the API sees them as stored.

**If it fails**, fix the cause and run the same command again. Every phase matches what it created before
(by name, by the `BreedCAFS item <uid>` unit description, or through its mapping file), so it carries on
from where it stopped. Exit code 2 is a settings or germplasm name conflict, printed as `Error:`;
exit code 1 is anything else, with the traceback in the log.

## 5. After the run

1. **Validate:**
   ```bash
   breedcafs-migration validate --user-id <migration user id> --team-id <migration team id>
   ```
   It only reads, writes `validation_report.md` to the data directory and exits with 3 if a check fails (README §8).
   Resolve failures before going on.
2. **Archive the curve files.** Their archival records are pending; the archive worker archives them once it runs.
3. **Take a backup** of the migrated database.
4. **Keep the artefacts** (README §13): the data directory with its mapping files and validation report, and the log,
   somewhere private, as they hold Person data. Then delete the bundle from the server, and uninstall the migration:
   `python -m pip uninstall breedcafs-migration`.

Everything stays `PRIVATE` under the migration team until handover (README §9–10),
which follows the DPO's review of the privacy notice and data processing terms.
