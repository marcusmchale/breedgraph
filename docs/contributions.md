# Contributions: design note

Status: **draft for review**.
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
- A CRediT role is created from its template (§3), with the CRediT name and definition.
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

Contributions are recorded per dataset, Program or Trial, not per record. A dataset is the unit that is cited, and per-record
attribution would multiply the graph for little gain.

## 3. Role templates

The CRediT roles are offered as **templates**, as countries are for root locations, rather than seeded into every ontology:
- A read model combines the stored Role entries that came from a template with the remaining templates from a packaged data file
  (`src/data/credit_roles.csv`: name, definition, role URL), as `countries` does with `country_codes.csv`.
- A query (`ontologyRoleTemplates`) returns the list. The front end offers it when creating a Role,
  and creating from a template fills in the name, the definition and the reference below.
- Creating a Role goes through the normal ontology commands, so only the roles a deployment uses are in its ontology.

### Attribution and licence

CRediT is published by NISO under **CC BY 4.0** (https://credit.niso.org/), which allows reuse of the definitions
with attribution: the creator, a link to the material, the licence with a link to it, and an indication of any changes.

A Role created from a template references a `PUBLIC` External Reference for its CRediT role:
- `url`: the role's page, e.g. `https://credit.niso.org/contributor-roles/data-curation/`
- `external_id`: the role's identifier in that URL, e.g. `data-curation`
- `description`: the attribution, as NISO asks it to be cited, with the licence:
  > National Information Standards Organization (2022). ANSI/NISO Z39.104-2022, CRediT, Contributor Roles Taxonomy. NISO. https://credit.niso.org/.
  > Definition licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/).

Creating a Role from a template reuses a readable External Reference with the same `url` if there is one, and creates it otherwise,
controlled by the creator's write team and released `PUBLIC`. The reference also marks the entry as a CRediT role for export.

A curator who changes a CRediT definition adds "Adapted from CRediT." to the description, as the licence asks changes to be indicated.
An extension that only borrows wording from a CRediT definition references the same External Reference.

| CRediT role | Fits datasets? |
|---|---|
| Investigation, Data curation, Methodology, Resources, Validation, Supervision | Yes |
| Conceptualization, Funding acquisition, Project administration | Better suited to Programs and Trials (§2) |
| Formal analysis, Software, Visualization, Writing – original draft, Writing – review & editing | Rarely; offered anyway |

All 14 are offered as templates. The front end can order them by fit.

## 4. BreedCAFS migration

BreedCAFS records give two sources of attribution (`breedcafs_migration/1_7_Extract_Persons.md`):
- the free-text `person` field, naming who recorded the data;
- the User who submitted it.

Only the submitter's role is known with confidence: they curated and uploaded the data, so every submitter is credited
with **Data curation**, to acknowledge that work. They may have had other roles, which are not recorded.
Submitters not yet mapped to a Person in `attribution_persons.csv` are added to the curation files, so they become Persons
like the others: `PRIVATE`, with the migration team as write team and the migration administrator's attestation.
The Persons named in `person` are credited **without roles**. Most of them recorded the data, but some values
name a supervisor or a group, and the migration does not try to tell them apart.
Roles can be added after the handover by the teams that receive control.

Where the submitter is also named in `person`, there is one contribution, with Data curation.

The migration ensures the Data curation Role exists, creating it from its template if needed.

## 5. Changes to other notes

- `person.md` §3, "Removed from the current model": the `Role` row says roles describing a Person stay removed, and points here for contribution roles.
- `person.md` §4: `Dataset.contributors` is replaced by contributions with roles (this note).
- `front-end-changes.md`: the API changes in §6.

## 6. Decisions

| Question | Decision |
|---|---|
| Vocabulary | `Role` ontology entries, based on CRediT and extended where needed. |
| Seeding | Not seeded. CRediT roles are offered as templates and created when used. |
| Contribution without roles | Allowed. Roles are declared, not exhaustive. |
| Granularity | Per dataset, not per record. |
| CRediT link and licence | A `PUBLIC` External Reference per CRediT role, with the NISO citation and the CC BY 4.0 licence (§3). |
| BreedCAFS | Every submitter gets Data curation, becoming a Person where not already one; Persons named in `person` get no roles. |
| Degree | Not recorded. CRediT allows lead / equal / supporting, but it is ambiguous, and BreedGraph should not be asked to settle disagreements over it. |
| Programs and Trials | Get contributions as datasets do, besides their contacts. |

| Removing a cited reference | Refused. A reference in use cannot be deleted: cited (`REFERENCE_FOR`, kept for earlier ontology versions after an entry drops it) or used as a licence or copyright (`USES_LICENCE`, `USES_COPYRIGHT`). |

## 7. Open questions

1. **Lowering the release of a CRediT reference.** The team controlling a shared CRediT reference can still lower its
   release, so other teams' Roles would cite a reference their readers cannot see.

## 8. Implementation plan

1. **Ontology.** `RoleBase/Input/Stored`, `OntologyEntryLabel.ROLE`, and the Role label in the ontology Cypher and query builders (restoring what `a8bad78` removed, with the new docstring).
2. **Templates.** `credit_roles.csv`, a `roles` read model alongside `countries`, the `ontologyRoleTemplates` query,
   and creating a Role from a template with its `PUBLIC` External Reference (§3).
3. **Domain.** `Contribution`; `Dataset.contributions` replacing `contributors`, and `contributions` on Program and Trial,
   with validation of the role ids in the handlers.
4. **Cypher and repository.** Roles on `CONTRIBUTED_TO` in the dataset, program and trial queries.
5. **GraphQL.** `ContributionInput { personId, roleIds }` replacing `contributorIds`; `Contribution { person, roles }` replacing `contributors: [Person]`;
   the same on Program and Trial. Dataset importer likewise.
6. **Tests.** The CRediT roles in `OntologyBuilder`, contributions with and without roles in the synthetic test database, which is rebuilt.
7. **Migration.** Submitters added to the Person curation files; Data curation for submitters, no roles for Persons named in `person` (§4).
