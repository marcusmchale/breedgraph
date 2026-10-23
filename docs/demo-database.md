# The demonstration database

A database of fictional winter wheat trials in Ireland, in plain English. It is built for:
- the University's data protection and legal offices, to look through on a hosted demonstration site;
- showing BreedGraph to outside users;
- breedview's user guide and its recordings, which walk through the same data.

It is built like the test database (docs/test-databases.md), through the repositories and with no message bus. Its
story is in `tests/breedgraph/scenarios/demo/`:
- `story.py` is data only: every name, team, account, place, entry, trial and dataset;
- `layout.py` lays out the trials;
- `values.py` makes the values and documents;
- `builder.py` writes it all;
- `manifest.py` describes what was built.

`tests/breedgraph/unit/test_demo_story.py` and `tests/breedgraph/integration/test_demo_scenario.py` check it.

Everything in it is invented. People have alliterative role names, so a viewer can tell who is acting, and their
addresses are at `example.org` (reserved, RFC 2606). The sites' coordinates are offsets from points on uninhabited
state-owned land, and the varieties' names are checked against the variety catalogues (below).

## The story

**Teams:**

| Team | Members (R read, W write, C curate, A admin; + heritable) |
|---|---|
| Example Plant Breeding Institute | Dara Data: A+, R+, C+, W |
| Wheat Breeding Group | Bridget Breeder: R, W, C, A; Theo, Lena: R |
| Field Operations | Theo Technician: R, W, C; Bridget, Lena: R. Rita Retired had R, W |
| Grain Quality Lab | Lena Lab: R, W, C, A; Bridget: R |
| Example Seed Cooperative (its own tree) | Petra Partner: A+, R+, C+, W |

**Accounts:**
- Dara is an ontology admin, Bridget an ontology editor, and Theo has asked to be an editor.
- Each account's username is its first name in lower case: `dara`, `bridget`, `theo`, `lena`, `petra`.
- Rita's account was deleted at the end of the build. Her Person is kept, and her writes show as "An account without
  a Person record".

**Persons:**
- Dara, Bridget, Theo and Lena have Persons linked to their accounts, released to registered users. Bridget's is the
  programme's contact.
- Petra's Person is unlinked, and her request to be linked to it is waiting for Bridget.
- Fergus Fieldhand is private, and credited on the 2024 and 2025 field data.
- Nina Newcomer is private and unlinked. The guide offers her the record when she is invited.
- One erased record, built under a neutral name.

**Places:**
- Ireland → County Offaly → Example Research Farm, which holds:
  - Long Meadow and North Field, public;
  - a Glasshouse, private;
  - the Grain Quality Laboratory, registered, with a private Sample Freezer.
- County Kildare holds the Cooperative's private farm and Seed Field.

**Germplasm:**
- Wheat is the crop.
- Six invented parent varieties: Copperwren, Fernhollow, Brindlecrest, Larkmere, Quillsprig and Harrowgold.
- Lines from hand crosses: EPB 19-031 and its siblings, public, and EPB 21-014 and its siblings, registered.
- EPB 25-S03 is a private single-plant selection that names the 2025 plant it came from.

**Ontology:**
- Plain English entries, each with a description, for:
  - the places, layouts and the randomised complete block design;
  - the field traits: plant height, heading date, yield and a Septoria score from 1 to 9;
  - the grain quality traits: thousand grain weight, protein and NIR spectra as files;
  - the nitrogen rate and fungicide programme factors.
- They were published in four versions after the seeded one, the last a patch to a description. No draft is left,
  because any later commit would publish it.

**Programmes:**
- Winter Wheat Breeding Programme, public:
  - **Preliminary Yield Trial 2024 → Long Meadow Yield Trial 2024:** public, licensed under the typed "Example Open
    Data Licence", with its field plan as a PDF. Eight entries in three randomised complete blocks, with height,
    heading, Septoria, yield and the fungicide programme. This is what visitors see.
  - **Advanced Yield Trial 2025:** private.
    - North Field Yield Trial 2025: eight entries at two nitrogen rates (48 plots).
    - Grain Quality 2025: the 48 grain samples, which reached the laboratory together (one arrival). It holds thousand
      grain weight (two counts each, in the "Grain count" grouping), protein (in "NIR run" batches) and eight NIR
      spectra.
- The Cooperative's private Seed Multiplication 2025.

The 2026 plots are sown in Long Meadow's layout, but no trial or study is built for them.

**Values:**
- They come from a model, not chance: each year's mean, plus the effects of the entry, nitrogen rate and block, plus
  noise from a hash of the value's key. So builds are identical, and analyses find real differences.
- Septoria is ordinal, so it gets descriptive statistics rather than ANOVA.

## The chains

The guide's workflows run in chains on a fresh load of the dump, so what one creates the next uses. The manifest's
`chains` give each chain's names, values and what must not exist yet (`absent`). The other workflows (`workflows`)
each start from the dump.

| Chain | Workflows | What it creates |
|---|---|---|
| Joining | invitation, team request, personal data | Nina Newcomer's account, invited with read and write access to Wheat Breeding Group and her Person; a request to read Grain Quality Lab, which Lena approves |
| This season | trial and study, recording, curation, analysis | Advanced Yield Trial 2026 and Long Meadow Yield Trial 2026; the 2026 heights, Septoria scores and nitrogen rates (pasted, with LM26-207's height typed with an extra zero, which curation corrects); an ANOVA |
| Next season | ontology, places, germplasm, planting | Flag leaf length (cm); Hill Field, with its boundary and layout; the cross EPB 26-X01; Hill Field's plots |

## Building

Build into throwaway services, so the dump comes from a fresh store and holds nothing written before. A dump also holds
the transaction logs and deleted records of the store it is taken from (docs/test-databases.md, "Building the public
dump"). `scripts/scratch_services.sh` runs a Neo4j and a Redis of your own in a scratch directory, on ports 7688 and
6380, without sudo:

```bash
set -a; . instance/breedgraph.env; . instance/private.breedgraph.env; set +a
SCRATCH=<scratch dir> scripts/scratch_services.sh build instance/neo4j_archive/demo_databases/demo_database.dump -- \
    .venv/bin/python scripts/build_demo_database.py \
        --manifest instance/neo4j_archive/demo_databases/demo_database.manifest.json \
        --password-file instance/private.demo_passwords.json
```

**Passwords:**
- `--password-file` is a JSON object of each account's password by username. Keep it among the instance's private
  files, which git ignores.
- `--password` gives every account one password, and `--generate` (the default) makes random ones.
- The passwords are written only to the manifest. The dump holds their bcrypt hashes.

The build writes three things beside the dump (all git-ignored under `instance/`):
- **The manifest**, readable by its owner only. It holds the accounts with their passwords, every entity by key (id,
  name, controls, and who reads it), the ontology's entries and versions, the units, the files, and the chains and
  workflows.
- **`demo_database_files/`**: the stored files (the field plans and the NIR spectra), to copy into `FILE_STORAGE_PATH`
  with the dump.
- **`demo_database_uploads/`**: the files the guide uploads (the partner licence and more spectra).

The build refuses Neo4j's development port (7687), and runs the study-licence and Person checks once it is done.

**Loading:**
- A recording or a check loads the dump into the throwaway services:

  ```bash
  scripts/scratch_services.sh load <dump> <files dir>
  ```

  This replaces the database, empties Redis, loads the state store and copies the files.
- `scripts/scratch_services.sh env` prints the environment that points breedgraph at them (`DB_PORT`, `REDIS_PORT` and
  the file and log paths). Use it, for example, with a second API started with `HOST_PORT=8001 VUE_PORT=8081`.

**Maps:** the build fetches no map regions, since there is no message bus. For detailed maps of the farm, fetch
Ireland's region once with `scripts/map_tiles.py --regions` (README, Maps).

## Checks before sharing a build

- **Variety names** (optional): the names are invented, and a name a real variety shares matters little in a
  demonstration. To compare them with exports of the variety catalogues (the EU Plant Variety Database, the UK
  National List and the Irish national catalogue), download those by hand, keep them out of git, and run:

  ```bash
  python scripts/check_demo_names.py src/data/variety_catalogues/*.csv
  ```

  It reports exact and close matches.
- **Places:** `test_demo_story.py` keeps every shape inside its site's box (`SITE_BOXES` in `story.py`). Check once by
  hand, on a map, that the boxes around the two origins (`ORIGINS`) hold no buildings, farmyards or dwellings, and
  record the date of the check here.
- **The story's tests**, which need no database:

  ```bash
  .venv/bin/python -m pytest --noconftest tests/breedgraph/unit/test_demo_story.py
  ```

  The integration test needs a database the suite may flush: point it at throwaway services with
  `eval "$(scripts/scratch_services.sh env)"`.
