# Contributions: design note

Status: **implemented** (2026-10-16), apart from rebuilding the test database dumps (§11, step 6).
This note records how Persons are credited for datasets, and the roles they had in that work.
It extends `person.md` §4, where `Dataset.contributors` was kept without a role.

## 1. Purpose

A dataset credits the Persons who contributed to it. A list of Persons says who, but not what they did.
Data often passes through several hands: one person records it in the field, another curates it and uploads it,
someone else supervised the work. Crediting each for their part is fairer, and lets the credit be exported to
systems that expect contributor roles (DataCite metadata, ORCID works).

A contribution is **a Person and the roles they had** in producing a dataset.
The roles are **declared, not exhaustive**:
- A contribution with no roles is allowed. It says the Person contributed, without saying how.
- A contribution with roles says the Person had at least those roles. They may have had others that were not recorded.

Roles can be added later, by whoever has write access to the dataset.

## 2. Model

### Role (ontology entry)

`Role` returns to the ontology, with a different meaning from the entry removed in `a8bad78`.
That entry described a Person ("Scientist", "Admin"), and was removed because a Person stores only what attribution needs (`person.md` §3).
The new `Role` describes **what a Person did in a contribution** ("Investigation", "Data curation").
It is stored on the contribution, never on the Person.

Roles are ordinary ontology entries: curated, versioned, with names, descriptions, synonyms and references.
They are based on the **CRediT** taxonomy (Contributor Roles Taxonomy, ANSI/NISO Z39.104-2022) and extended where needed:
- The 14 CRediT roles are seeded into the ontology and locked (§3, §4).
- An extension is a new `Role` entry. Where it refines a CRediT role it is placed under it with `PARENT_OF`,
  e.g. "Sample collection" under Investigation, so credit can be rolled up to standard roles when exporting.
- DataCite `contributorType` names (DataCollector, DataCurator, ...) can be given as synonyms where they match.

### Contribution

```
Contribution
  person: int           # PersonStored id
  roles: List[int]      # Role ontology entry ids, possibly empty
```

`Dataset.contributors: List[int]` becomes `Dataset.contributions: List[Contribution]`, at most one per Person.
It is stored on the existing relationship: `(Person)-[:CONTRIBUTED_TO {roles: [...]}]->(Dataset)`.
Erasing a Person keeps the relationship and its roles, attributed to the anonymous id (`person.md` §5).

Validation: each role must be an existing `Role` entry in the ontology. A Person appears once per dataset.

Programs and Trials get contributions in the same way, besides their contacts, for the roles that fit them better
than datasets (Conceptualization, Funding acquisition, Project administration, Supervision).

File, data file and external data references get contributions too: they are often made in the project,
e.g. a data summary cited by a study, a figure or report, or the project's data deposited elsewhere, and the CRediT roles
that rarely fit a dataset fit them (Formal analysis, Visualization, Writing, Software). External references (papers,
web pages) and legal references do not: the authors of a cited work are part of its citation, and are not Persons
(`person.md` §1). The contributions are set in the references' create and update inputs.

Contributions are recorded per dataset, Program, Trial or reference, not per record. A dataset is the unit that is cited, and per-record
attribution would multiply the graph for little gain.

## 3. Seeded CRediT roles

CRediT is a fixed external standard, so its roles are **seeded** with the "Country" location type,
rather than created by each deployment:
- The roles are a packaged data file, `src/breedgraph/data/credit_roles.csv` (name, external id, role URL, definition),
  with the definitions as published by NISO.
- They are created by `seed_ontology` (`service_layer/application/ontology_seed.py`) as the system user, in the initial version:
  `scripts/setup_initial_data.py` for a deployment, and the test setup. It creates only entries missing by name.
- Each is created **locked** (§4), with the CRediT definition as its description and a `source` (§5) giving its CRediT URL and attribution.
- Every seeded entry, Country included, is also given a **seed key** (`country`, `credit:data-curation`, ...), set only by seeding.
  Code finds a seeded entry by its key, never by name, as an admin may unlock and rename it; once found it is referred to by id,
  which the referential view resolves in any phase. Seeding creates only entries whose key is missing.
  Country was protected before by a lifecycle quirk (version 0.0.0, before the first commit, read back as no version,
  so its entry seemed never drafted and could not be deprecated); the lock replaces it.

| CRediT role | Fits datasets? |
|---|---|
| Investigation, Data curation, Methodology, Resources, Validation, Supervision | Yes |
| Conceptualization, Funding acquisition, Project administration | Better suited to Programs and Trials (§2) |
| Formal analysis, Software, Visualization, Writing – original draft, Writing – review & editing | Rarely |

All 14 are seeded. The front end can order them by fit.

### Attribution and licence

CRediT is published by NISO under **CC BY 4.0** (https://credit.niso.org/), which allows reuse of the definitions
with attribution: the creator, a link to the material, the licence with a link to it, and an indication of any changes.
Each seeded Role's `source` gives its role page as the URL and, as the attribution, NISO's citation with the licence:
> National Information Standards Organization (2022). ANSI/NISO Z39.104-2022, CRediT, Contributor Roles Taxonomy. NISO. https://credit.niso.org/.
> Definition licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/).

The entries are locked, so the definitions stay unchanged. If an admin unlocks one and changes its definition,
they add "Adapted from CRediT." to the description, as the licence asks changes to be indicated.

## 4. Locking ontology entries

Any ontology entry can be **locked** by an ontology admin, and unlocked by one. Seeded entries start locked.
Locking is for entries that follow an external standard, or that much depends on, so they stay stable.

A locked entry:
- keeps its name, abbreviation, description and `source`;
- cannot be deprecated;
- keeps the relationships that define it: those from it to other entries, other than to its children and terms,
  e.g. a locked variable keeps its trait, method and scale, and a locked scale its categories.

Still open on a locked entry: synonyms, references, children (e.g. "Sample collection" under Investigation), terms,
and relationships from other entries to it (e.g. variables using a locked scale).

The lock is a property of the entry, not of a version: it applies from when it is set, and is shown as `locked` in GraphQL.
Locking and unlocking are recorded with the user and time, as `(User)-[:LOCKED]->(:UserOntologyLocks)-[:LOCKED {time, locked}]->(entry)`.
A lock is attributed but is not a contribution to the entry, and a lock or unlock that leaves the entry as it was records nothing.

## 5. Sources of ontology entries

An ontology entry may have a `source`: a URL and an attribution line, for an entry taken from an external standard or ontology
(CRediT here; Crop Ontology terms, for example, later). Unlike references, a source is not a controlled aggregate:
the ontology is shared, so the source is shown with the entry to everyone who can see it, and no release can hide it.
Editors set it like other attributes; it is fixed while the entry is locked.

## 6. Releases of cited references

A reference that is in use cannot be deleted (`guards/reference_in_use.cypher`): cited, or used as a licence or copyright.
In the same way, **a reference's release cannot be lowered below the release of what cites it**, so a change by the reference's
controllers never hides a citation from those who can see what cites it. The ontology counts as `PUBLIC`.
Raising a release is always allowed, and a reference no longer cited is free again.

This complements read-access rule 2 (placeholders): a citation of a reference that some readers cannot see still shows to them
as a placeholder, but a citation cannot be turned into one later by lowering the reference's release.

## 7. BreedCAFS migration

BreedCAFS records give two sources of attribution (`breedcafs_migration/1_7_Extract_Persons.md`):
- the free-text `person` field, naming who recorded the data;
- the User who submitted it.

Only the submitter's role is known with confidence: they curated and uploaded the data, so every submitter is credited
with **Data curation**, to acknowledge that work. They may have had other roles, which are not recorded.
Submitters are mapped to Persons in a third curation file, `submitter_persons.csv`, drafted from the submissions;
any not yet in `persons.csv` are added there, so they become Persons like the others: `PRIVATE`, with the migration team
as write team and the migration administrator's attestation.
The Persons named in `person` are credited **without roles**. Most of them recorded the data, but some values
name a supervisor or a group, and the migration does not try to tell them apart.
Roles can be added after the handover by the teams that receive control.

Where the submitter is also named in `person`, there is one contribution, with Data curation.

The Data curation Role is seeded (§3), so the migration finds it by name.

## 8. Changes to other notes

- `person.md` §3, "Removed from the current model": the `Role` row says roles describing a Person stay removed, and points here for contribution roles.
- `person.md` §4: `Dataset.contributors` is replaced by contributions with roles (this note).
- `docs/read-access.md`: citing a reference needs read access, and the release rule (§6). Done.
- `front-end-changes.md`: the API changes in §11.

## 9. Decisions

| Question | Decision |
|---|---|
| Vocabulary | `Role` ontology entries, based on CRediT and extended where needed. |
| Seeding | The 14 CRediT roles are seeded, locked, with a `source` giving the CRediT URL and attribution (§3). |
| Locking | Any ontology entry can be locked and unlocked by ontology admins (§4). |
| Contribution without roles | Allowed. Roles are declared, not exhaustive. |
| Granularity | Per dataset, not per record. |
| CRediT link and licence | The entry's `source`, with the role URL, the NISO citation and the CC BY 4.0 licence (§3, §5), not a controlled reference. |
| BreedCAFS | Every submitter gets Data curation, becoming a Person where not already one; Persons named in `person` get no roles. |
| Degree | Not recorded. CRediT allows lead / equal / supporting, but it is ambiguous, and BreedGraph should not be asked to settle disagreements over it. |
| Programs and Trials | Get contributions as datasets do, besides their contacts. |
| References | File, data file and external data references get contributions; external and legal references do not (§2). |
| Removing a cited reference | Refused. A reference in use cannot be deleted: cited (`REFERENCE_FOR`, kept for earlier ontology versions after an entry drops it) or used as a licence or copyright (`USES_LICENCE`, `USES_COPYRIGHT`). |
| Lowering a cited reference's release | Refused below the release of what cites it; the ontology counts as `PUBLIC` (§6). |
| Citing a reference | Requires read access to it (`docs/read-access.md`, rule 10); on updates, only references added are checked. |

## 10. Open questions

None.

## 11. Implementation plan

1. **Ontology.** Done: `RoleBase/Input/Stored`, `OntologyEntryLabel.ROLE`, create and update commands, links to terms, and the GraphQL `Role` type.
2. **Locking and sources.** Done: `locked` and `source` on ontology entries; lock and unlock commands for ontology admins;
   updates, deprecation and defining relationships of locked entries refused (§4, §5).
2b. **Seeding.** Done: `credit_roles.csv` seeded as locked Roles with their source, with the initial data (§3).
2c. **Reference releases.** Done: lowering a reference's release below that of what cites it is refused (§6).
3. **Domain.** Done: `Contribution`; `Dataset.contributions` replacing `contributors`, and `contributions` on Program and Trial,
   with validation of the role ids in the handlers.
4. **Cypher and repository.** Done: roles on `CONTRIBUTED_TO` in the dataset, program and trial queries.
5. **GraphQL.** Done: `ContributionInput { personId, roleIds }` replacing `contributorIds`; `Contribution { person, roles }` replacing `contributors: [Person]`;
   the same on Program and Trial. Dataset importer likewise.
6. **Tests.** Done: the seeded CRediT roles in the test fixtures, and contributions with and without roles in the read-policy scenario.
   The test database dumps are to be rebuilt (`docs/test-databases.md`).
7. **Migration.** Done: Data curation for submitters, mapped to Persons in `submitter_persons.csv`, which the bundle carries;
   no roles for Persons named in `person` (§7). `submitter_persons.csv` is curated for the BreedCAFS and rehearsal data;
   the rehearsal is to be rerun on the rebuilt test database.
8. **References.** Done: contributions on file, data file and external data references, in their create and update inputs.
