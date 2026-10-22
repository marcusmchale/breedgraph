# Front-end changes

The API changes the front end (`breedview`) has yet to make, with what breaks and the work each needs. Field names are
given as in GraphQL (camelCase). A section is removed once breedview implements it; the earlier ones (Persons,
invitations, transfers, record group extents, the renamed areas, contributions, times, bulk control, Person views and
maps) are in this file's history, last in full at `021f830` (`git show 021f830:docs/front-end-changes.md`), the two
after them (removing optional links with null, units as record group levels) at `7549579`, the three after those
(arrivals, inherited germplasm, moving units) at `a5c7625`, germplasm entries from units at `fd0c50d`, legal references given as files at `81961e6`, the Terms of Use at `1ae91b7`, accepting study licences at `de74a78`, and the privacy notice from the API at `8f48104`. Where they
describe the API rather than the work, the schema's descriptions, README.md and the design notes in `docs/` have it.

## Where the front end is

breedview's master (`5d78ad9`) implements every API change up to 2026-10-22, except derived units (below).

**For the next API change:** add a section for it, with what breaks and the work it needs; then, in breedview,
regenerate the schema files with the API running (`node scripts/fetchGraphqlSchema.js` writes `schema.graphql`,
`possibleTypes.json` and `unionTypes.json`) and run the check script below.

## Derived units

A unit can be derived from others: material that starts a context of its own, e.g. plantlets in a field grown from
microcuttings that arrived from a lab (README, Unit). Unlike a parent, a unit derived from passes nothing down. Nothing
breaks: every change adds to the schema, and a unit with units derived from it can no longer be deleted.

- `Unit.derivedFrom` and `Unit.derivatives`: lists of `UnitDerivation { unit, sourceType, description }`, where `unit`
  is the other end of the link (a placeholder in `derivedFrom` where hidden; `derivatives` lists readable units only).
  Work: show both on a unit's page, as its history and where its material went, apart from parents and children.
- `UnitInput.derivedFrom` and `UnitUpdate.derivedFrom`: `[UnitDerivationInput!]` of `{ unitId, sourceType, description }`
  (`sourceType` defaults to UNKNOWN). On update, omitted leaves them unchanged and an empty list removes them all. Refused
  for the unit itself, the units above or below it in its unit graph, and units derived from it. Work: a picker in the
  unit form, with the child-or-derived guidance from the README (a sample stays a child of its tree).
- `unitsDeleteUnit` is refused for a unit with units derived from it ("Units are derived from this unit"). Work: show
  the message.

## Checking the front end against the API

```bash
set -a; . instance/breedgraph.env; . instance/private.breedgraph.env; set +a
.venv/bin/python scripts/check_front_end_queries.py ../breedview/src
```

It builds the API's schema and validates every operation in the front end's `.graphql` files, with the fragments each uses, and exits with 1 if any fails.
It does not check variables, so input fields built in JavaScript (as `roleIds` was) need a search.
Rerun it after changing the front end, and after any API change, before releasing either.
