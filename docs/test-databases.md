# Test databases

Two Neo4j dumps for development, kept in `NEO4J_ARCHIVE_PATH` (`instance/neo4j_archive/`, not in git), each with a
manifest and the files its references point to:

| Dump | What it holds | Sharing |
|---|---|---|
| `test_database.dump`, `test_database.manifest.json`, `test_database_files/` | The read-policy scenario of the tests, generated, optionally with data at scale | **Public**: synthetic, with known credentials. breedview's e2e and performance tests run against it |
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
   scripts/restore.sh test_database.dump
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
   cp instance/neo4j_archive/test_database_files/* "$FILE_STORAGE_PATH"/
   ```
   (`test_database_breedcafs_files/` for the BreedCAFS dump.)

Then start the API (`uvicorn src.breedgraph.main:app`) and log in with an account above.

## Building the public dump

The build runs on an empty Neo4j and Redis, which a run of the test suite leaves:

```bash
set -a; . instance/breedgraph.env; . instance/private.breedgraph.env; set +a
python scripts/build_test_database.py --manifest instance/neo4j_archive/test_database.manifest.json --scale
```

- It sets the database up as `setup_initial_data.py` would, builds the read-policy scenario
  (`tests/breedgraph/scenarios/read_policy_scenario.py`) without the message bus, so no email is sent, and refreshes
  the read models.
- `--scale` adds data at scale for breedview's performance scripts (`scale_scenario.py`): with the defaults,
  20 fields, 100,020 units and 44,000 records. The sizes can be set (`--fields`, `--trees-per-field`, …).
  The manifest's `perf` entry names the study, concept and field those scripts use.
- `--seed` (default 1) seeds the generated names, so a build is repeatable.
- It refuses to overwrite an existing manifest: move the old one aside, or build to another path.
- The manifest records the commit it was built from (`breedgraph_commit`).

Then dump it, with `sudo` as Neo4j is stopped:

```bash
scripts/backup.sh
```

and rename the dump it reports (`neo4j-<date>.dump`) to `test_database.dump`, beside the manifest.

## Building the BreedCAFS dump

The BreedCAFS dump is a rehearsal of the migration (`src/breedcafs_migration/RUNBOOK.md` §1) on a fresh public
build. It needs the extracted BreedCAFS data in `src/data/breedcafs_migration/`, and the production germplasm in
`src/data/germplasm/`.

1. Build the public database as above, or restore it. A build to another manifest path leaves the public dump's
   files alone:
   ```bash
   python scripts/build_test_database.py --manifest <scratch>/rehearsal_base.manifest.json --scale
   ```
2. Rehearse. Move any earlier `src/data/breedcafs_migration_rehearsal/` aside first: its mapping files belong to
   the database it was made on, and a rehearsal uses an existing directory as it is.
   ```bash
   python scripts/rehearse_migration.py --manifest <scratch>/rehearsal_base.manifest.json 2>&1 | tee rehearsal.log
   ```
   It creates the rehearsal team with a legal entity, loads the germplasm, bundles and unbundles the data into
   `src/data/breedcafs_migration_rehearsal/`, runs bootstrap, migrate and validate, and exits with the validation's
   status. The validation report is in that directory.
3. Dump with `scripts/backup.sh`, and rename the dump to `test_database_breedcafs.dump`.
4. Copy the base build's manifest to `test_database_breedcafs.manifest.json`, and gather its files into
   `test_database_breedcafs_files/`: the base build's files (beside its manifest), and the four curve data files
   the migration wrote to `FILE_STORAGE_PATH`. Their ids are the `file_id` of the curve references, whose ids are
   in `src/data/breedcafs_migration_rehearsal/curve_ids.csv`.

The rehearsal's data directory, mapping files and validation report hold Person data: keep them in `src/data/`,
which is not in git, and never in a shared location.
