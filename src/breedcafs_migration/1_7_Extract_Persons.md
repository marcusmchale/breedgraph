## 1.7. Extract Persons

Person data stays in the untracked `src/data/breedcafs_migration/` directory. Do not copy names into these notes or into git.

### 1.7.1 Who recorded the data

BreedCAFS has two sources of attribution for a Record:
  - the free-text `person` field, naming who recorded the data. Almost every record has one.
  - the User who submitted it, through `(User)-[:SUBMITTED*4]->(Record)`.
    A few users uploaded data for many people, so submitters do not reflect who did the work.

We attribute by `person`, and fall back to the submitter only where `person` is empty.

Each User has exactly one `AFFILIATED` Partner with `data_shared: true`.
The `person` value does not record a Partner, so the submitters' Partners are extracted as suggestions for curation.

### 1.7.2 Deleted records

Records deleted in BreedCAFS are detached from their ItemInput:
```cypher
(:Deletions)-[:DELETED]->(r:Record)-[:DELETED_FROM]->(:ItemInput)
```
Matching on `RECORD_FOR` excludes them, as do the queries in the other extraction steps.
Records of "Assign sample to block(s) by name" whose items no longer exist have no `FOR_ITEM`, and that property is not migrated anyway (1.5).

### 1.7.3 Submissions

A submission is the set of records a User submitted at one time, `(:UserFieldInput)-[:SUBMITTED {time}]->(:Record)`.
Each has one submitter, and so one Partner. Most submissions have one attribution value; some have two or three.

[extract_submissions.cypher](cypher/extract_submissions.cypher) gives one row per submission, input and attribution value,
with the submitter's Partner, record count and fields.
The attribution is the trimmed `person` value or, where that is empty, `submitter: <user name>`.
Records loaded without a submission (the photosynthesis data) have no submission time, submitter or Partner.
Datasets are attributed from these rows: the records of an input submitted together, and the Persons who recorded them.

Saved this as submissions.csv

### 1.7.4 Partners

[extract_partners.cypher](cypher/extract_partners.cypher) gives the short and full name of each Partner.
The full name is used as the Person's institution.

Saved this as partners.csv

### 1.7.5 Curate

Curation is in two files.

attribution_persons.csv maps each attribution value to the Persons it refers to.
The same value submitted through different Partners may be different people,
so it has one row per attribution value and Partner, as in submissions.csv, with the record, submission and input counts.

  - `Name` lists every Person the value refers to, separated by `;`. Leave it empty to leave those records unattributed.
  - Keep `attribution` and `partner` unchanged: they are the key back to the records in submissions.csv.
    Records loaded without a submission have an empty `partner`.

persons.csv defines each Person once, by `Name`, with its `institution`.

  - `Name` is the key used in attribution_persons.csv, so it must be unique across all Persons and spelled identically in both files.
    Full names are not always known; the name can be refined later.
  - `institution` is the full name of the Partner the person worked with (partners.csv).
    It is not always the submitter's Partner: a colleague at another Partner may have submitted the data.
  - `other_institutions` lists other institutions found for the name, to be resolved and then cleared.
  - No other personal data (username, email, role) is kept.

### 1.7.6 Use during creation

Each row of persons.csv becomes a `PRIVATE` Person with its name and institution,
with the migration team as write team and the informed attestation given by the migration administrator.
Datasets are built from the rows of submissions.csv, and each dataset's contributors are the Persons
named for its rows' attribution value and Partner in attribution_persons.csv.
The mapping from name to Person id is saved as person_ids.csv, alongside the other Person files.
