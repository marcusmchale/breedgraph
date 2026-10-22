# Front-end changes

The API changes the front end (`breedview`) has yet to make, with what breaks and the work each needs. Field names are
given as in GraphQL (camelCase). A section is removed once breedview implements it; the earlier ones (Persons,
invitations, transfers, record group extents, the renamed areas, contributions, times, bulk control, Person views and
maps) are in this file's history, last in full at `021f830` (`git show 021f830:docs/front-end-changes.md`), the two
after them (removing optional links with null, units as record group levels) at `7549579`, the three after those
(arrivals, inherited germplasm, moving units) at `a5c7625`, germplasm entries from units at `fd0c50d`, legal references given as files at `81961e6`, and the Terms of Use at `1ae91b7`. Where they
describe the API rather than the work, the schema's descriptions, README.md and the design notes in `docs/` have it.

## Where the front end is

breedview's master (`1085d91`) implements every API change up to the Terms of Use (2026-10-22).

**For the next API change:** add a section for it, with what breaks and the work it needs; then, in breedview,
regenerate the schema files with the API running (`node scripts/fetchGraphqlSchema.js` writes `schema.graphql`,
`possibleTypes.json` and `unionTypes.json`) and run the check script below.

## Accepting study licences

A study's data is given only to those who accepted its licence at its current text, unless they read the dataset or
its study through a controlling team (docs/licences.md §5). New:

- `Dataset.licence: LegalReference` (the study's licence) and `Dataset.licenceRequired: Boolean!`.
- `LegalReference.accepted: Boolean!`: whether the request carries an acceptance of its current text.
- `licencesAccept(licences: [LicenceAcceptanceInput!]!)`, each `{ id, contentHash }`: all or none, refused for a licence
  changed since it was read. It updates the acceptance cookie the Terms of Use use.

What breaks, for a licensed dataset the user must accept the licence of: `records` and `dimensions` are null, with
GraphQL errors on those fields; `analysisSubmit` is refused with `LICENCE_NOT_ACCEPTED` at `['datasetIds', i]`; and
`referencesFileDownload` is refused for files its records cite (`LicenceNotAcceptedError`).

Work in breedview: before Load Table in curation, and before submitting an analysis, read the chosen datasets'
`licence` and `licenceRequired`, show the licences still to accept with one box to tick and Accept, calling
`licencesAccept`, then read them again; show a download's refusal.

## Checking the front end against the API

```bash
set -a; . instance/breedgraph.env; . instance/private.breedgraph.env; set +a
.venv/bin/python scripts/check_front_end_queries.py ../breedview/src
```

It builds the API's schema and validates every operation in the front end's `.graphql` files, with the fragments each uses, and exits with 1 if any fails.
It does not check variables, so input fields built in JavaScript (as `roleIds` was) need a search.
Rerun it after changing the front end, and after any API change, before releasing either.
