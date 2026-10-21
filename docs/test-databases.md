# Test databases

Two Neo4j dumps for development, kept in `test_databases/` under `NEO4J_ARCHIVE_PATH`
(`instance/neo4j_archive/test_databases/`, not in git), each with a manifest and the files its references point to:

| Dump | What it holds | Sharing |
|---|---|---|
| `test_database.dump`, `test_database.manifest.json`, `test_database_files/` | The read-policy scenario of the tests and its replicates study, generated, optionally with data at scale | **Public** when built from a fresh store (below): synthetic, with known credentials. breedview's e2e and performance tests run against it |
| `test_database_breedcafs.dump`, `test_database_breedcafs.manifest.json`, `test_database_breedcafs_files/` | The same scenario plus a rehearsal of the BreedCAFS migration | **Private**: BreedCAFS data and Person data, `PRIVATE` under the migration team. Never share it or publish it like the public dump |

There is one Neo4j instance (Community allows one active database). The dev database is switched between dumps
by restoring them. The test suite runs on the same database and wipes it (`MATCH (n) DETACH DELETE n`, and
`flushdb` on Redis) at module setup and teardown, so restore what you need after a suite run, and never run the
suite while a dump you care about is loaded and not yet saved.

## Accounts

Both dumps have the scenario's accounts, all verified, with `example.org` addresses and the same password,
`readpolicy-test-password` (the build's `--password`):

| Account | Access |
|---|---|
| `readpolicy_admin` | ADMIN, CURATE, READ and WRITE on the scenario's root team; ADMIN and READ on its child |
| `readpolicy_writer` | CURATE, READ and WRITE on the child team |
| `readpolicy_stranger` | All access to an unrelated team |
| `readpolicy_outsider` | No affiliation |

The manifest gives each account's id, and every entity's id, label, controls and readers by its scenario name.
In the BreedCAFS dump, `readpolicy_admin` is also a heritable admin of the "BreedCAFS Rehearsal University" team,
which has the BreedCAFS Migration team under it, so it reads the migrated data.

## Restoring a dump

Restoring needs `sudo`, as Neo4j is stopped while the dump is loaded.

1. **Restore:**
   ```bash
   set -a; . instance/breedgraph.env; . instance/private.breedgraph.env; set +a
   scripts/restore.sh test_databases/test_database.dump
   ```
   `restore.sh` then replays the erasure log. Each entry is applied only to the record with its id and creation time
   (docs/person.md §5), and the test database's Persons and accounts were created at other times, so the log's
   erasures, logged for another database, leave them alone; they are reported as reissued ids.
2. **Load the state store** (the countries read model):
   ```bash
   python scripts/load_state_store.py
   ```
3. **Copy the files** beside the dump into the file store, so references to them resolve:
   ```bash
   cp instance/neo4j_archive/test_databases/test_database_files/* "$FILE_STORAGE_PATH"/
   ```
   (`test_database_breedcafs_files/` for the BreedCAFS dump.)

Then start the API (`uvicorn src.breedgraph.main:app`) and log in with an account above.

## Building the public dump

**Start from a fresh store**, not just an empty database, if the dump may be shared. A dump holds every transaction
log Neo4j keeps (`db.tx_log.rotation.retention_policy`, by default 2 days or 2 GB) as well as the store, and the store
keeps the bytes of deleted records until they are overwritten. An emptied dev database still holds, in both, whatever
was written before: the test suite's BreedCAFS migration tests write real BreedCAFS data. The dumps of 2026-10-16
were built without this step, and each holds about 2.5 GB of such logs (uncompressed). With Neo4j stopped, remove the
database's store and logs, and Neo4j creates an empty database when it starts (`sudo`):

```bash
sudo service neo4j stop
sudo rm -r /var/lib/neo4j/data/databases/neo4j /var/lib/neo4j/data/transactions/neo4j
sudo service neo4j start
```

(The paths are `server.directories.data` in `/etc/neo4j/neo4j.conf` and `DATABASE_NAME`. Dump anything you want to keep
first.) The build also needs an empty Redis: flush it if the test suite has not just run. Then build:

```bash
set -a; . instance/breedgraph.env; . instance/private.breedgraph.env; set +a
python scripts/build_test_database.py --manifest instance/neo4j_archive/test_databases/test_database.manifest.json --scale
```

- It sets the database up as `setup_initial_data.py` would, builds the read-policy scenario
  (`tests/breedgraph/scenarios/read_policy_scenario.py`) without the message bus, so no email is sent, and refreshes
  the read models.
- The scenario's location trees are in Iran and Isle of Man, and its field, centre, lab and registered field have
  made-up coordinates on the Qazvin plain (`LOCATION_COORDINATES`), so the location map shows pins and a polygon;
  the states have none. Detailed maps of these countries come from `scripts/map_tiles.py --regions` (README.md,
  Maps), as the build sends no events.
- It adds the replicates study (`replicate_scenario.py`, below) and the arrivals (`arrival_scenario.py`, below).
- `--scale` adds data at scale for breedview's performance scripts (`scale_scenario.py`): with the defaults,
  20 fields, 100,115 units and 44,000 records, each field a made-up plot beside the scenario's field. Field 02's trees
  are positioned at their field themselves, and the first five trees of every field but 01 each hold a sample at a
  scale lab from one date: one arrival of 95 units from 19 unit graphs. The sizes can be set (`--fields`,
  `--trees-per-field`, `--samples-per-field`, …).
  The manifest's `perf` entry names the study, concept and field those scripts use.
- `--seed` (default 1) seeds the generated names, so a build is repeatable.
- It refuses to overwrite an existing manifest: move the old one aside, or build to another path.
- The manifest records the commit it was built from (`breedgraph_commit`).

Then dump it, with `sudo` as Neo4j is stopped:

```bash
scripts/backup.sh
```

and move the dump it reports (`neo4j-<date>.dump`, in `NEO4J_ARCHIVE_PATH`) beside the manifest as
`test_databases/test_database.dump`. With `ENCRYPTION_RECIPIENT` set, `backup.sh` writes an encrypted
`neo4j-<date>.dump.age` instead: the test database is public, so dump it with `ENCRYPTION_RECIPIENT= scripts/backup.sh`.

### The replicates study

A study of record group codes of every extent and scope, for checking curation and replicate aggregation
(`tests/breedgraph/scenarios/replicate_scenario.py` has the records). It is controlled by the child team and released
REGISTERED, so every account reads it, and `readpolicy_writer` curates it.

- **Path:** "Readpolicy replicates program" → "Readpolicy replicates trial" → "Readpolicy replicates study".
- **Units:** two unit graphs, "Rep Field A" and "Rep Field B", each a field with two plots ("Rep Plot A1", "Rep Plot
  A2", …) of three trees ("Rep A1" to "Rep A6", "Rep B1" to "Rep B6").
- **Groupings,** one per extent and scope:

  | Grouping | Type | Extent | Scope |
  |---|---|---|---|
  | Dataset Scoped Replicate | Replicate | WITHIN_UNIT | dataset-scoped; `same_time` and `width` share a scope |
  | Study Scoped Biological Replicate | Biological Replicate | WITHIN_UNIT | study-wide |
  | Study Scoped Batch | Batch | SHARED | study-wide |
  | Dataset Scoped Plate | Plate | SHARED | dataset-scoped; `same_time` and `width` share a scope |
  | Study Scoped Block | Block | WITHIN_GRAPH | study-wide; "Block 1" and "Block 2" in each field |
  | Dataset Scoped Block | Block | WITHIN_GRAPH | dataset-scoped |

- **Datasets,** every record with its unit's Study Scoped Block code:

  | Key | Concept | Records |
  |---|---|---|
  | `same_time` | Tree Height (mm) | Replicates 1–3 of each tree at one start, 1–2 of Rep A6; Plate A or B by plot |
  | `width` | Canopy Width (mm) | The same trees, starts and codes as `same_time` |
  | `windowed` | Tree Height (mm) | Replicates 1–3 of each tree at 10:00, 10:03 and 10:20 on one date |
  | `dated` | Tree Height (mm) | Replicates 1–3 of each tree on three dates |
  | `biorep`, `biorep_width` | Tree Height, Canopy Width | Biological replicates 1–2 of each tree at one start |
  | `factor` | Light | One undated record per plot |
  | `blocks` | Tree Height (mm) | Each tree once, with Batch 1 or 2 across the fields |
  | `regrouped` | Tree Height (mm) | Each tree once, with Dataset Scoped Block "Block A" or "Block B" |

The manifest's `replicates` entry gives the ids of the program, trial, study, groupings (with type, extent and scope),
datasets (with concept, record count and the units with replicates), units by name and concepts. Its `expected`
entry gives what analyses report, checked by `tests/breedgraph/e2e/analysis/test_replicate_analyses.py`:

- `cases`: for an analysis of one dataset's concept with no dimensions, by aggregation and replicate aggregation, the
  error (code, the end of its path, the number of records) or the warnings;
- `windowed_readings_per_tree`: readings per tree in `windowed`, with no window, `PT5M` and `PT1H`;
- `plot_means`: `same_time` by plot (`grouping.unit`) with a term MEAN, pooled and as the mean of tree means;
- `levels`: the nested level keys (docs/analysis.md §6) of a record group dimension of each grouping, by dataset;
- `blocks`: the Block levels of `blocks`, with "Block 1" shared, and its Batch levels.

### The arrivals

Units that came to locations at dated positions, for the Units page's arrivals, moving units in bulk, and germplasm
and factors coming down the unit graph (`tests/breedgraph/scenarios/arrival_scenario.py` draws them). Controlled by
the child team and released REGISTERED, so every account reads them and `readpolicy_writer` curates them, except
"Arrival Sample Hidden", which is PRIVATE: only the admin and the writer read it.

- **Locations:** "Arrival Lab Store", below the scenario's lab.
- **Units:** one unit graph, "Arrival Field" at the registered field, with a plot of four trees. Samples of Tree A and
  Tree B reached the lab on 2025-03-25; one was taken from a sample there; one moved on to the lab store on
  2025-05-02 and one was used up; Tree B visited the lab in 2024 and went back; "Arrival Pooled" is from Tree A and
  Tree B, whose germplasm differ, "Arrival Pooled Same" from Tree A and Tree C, whose agree. The hidden sample's
  extract is an arrival for whoever can't read the sample. Two samples of "Arrival Move Tree" reached the lab on
  2025-06-10, for tests that move them and put them back.
- **Study:** "Readpolicy arrivals program" → "trial" → "study", with the light factor on the trees and the height
  variable on samples.

The manifest's `arrivals` entry gives the ids of the program, trial, study, locations, units by name and datasets.
Its `expected` entry gives each location's arrivals as each viewer sees them (start as entered, null for undated,
newest first; units by name), the germplasm each unit takes and the unit it comes from, and the light that describes
each height record (none for "Arrival Pooled", its trees' records differing).

## Building the BreedCAFS dump

The BreedCAFS dump is a rehearsal of the migration (`src/breedcafs_migration/RUNBOOK.md` §1) on a fresh public
build. It needs the extracted BreedCAFS data in `src/data/breedcafs_migration/`, and the production germplasm in
`src/data/germplasm/`.

1. Build the public database as above, or restore it, or rehearse straight after dumping the public build, on the
   same database and with its manifest (as on 2026-10-16). A build to another manifest path leaves the public dump's
   files alone:
   ```bash
   python scripts/build_test_database.py --manifest <scratch>/rehearsal_base.manifest.json --scale
   ```
2. Rehearse. Move any earlier `src/data/breedcafs_migration_rehearsal/` aside first: its mapping files belong to
   the database it was made on, and a rehearsal uses an existing directory as it is.
   ```bash
   python scripts/rehearse_migration.py --manifest <scratch>/rehearsal_base.manifest.json 2>&1 | tee rehearsal.log
   ```
   It creates the rehearsal team, loads the germplasm, bundles and unbundles the data into
   `src/data/breedcafs_migration_rehearsal/`, runs bootstrap, migrate and validate, and exits with the validation's
   status. The validation report is in that directory.
3. Dump with `scripts/backup.sh`, and move the dump to `test_databases/test_database_breedcafs.dump`.
4. Copy the base build's manifest to `test_databases/test_database_breedcafs.manifest.json`, and gather its files into
   `test_database_breedcafs_files/`: the base build's files (beside its manifest), and the four curve data files
   the migration wrote to `FILE_STORAGE_PATH`. Their ids are the `file_id` of the curve references, whose ids are
   in `src/data/breedcafs_migration_rehearsal/curve_ids.csv`.

The rehearsal's data directory, mapping files and validation report hold Person data: keep them in `src/data/`,
which is not in git, and never in a shared location.
