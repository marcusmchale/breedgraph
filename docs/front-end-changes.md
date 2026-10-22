# Front-end changes

The API changes the front end (`breedview`) has yet to make, with what breaks and the work each needs. Field names are
given as in GraphQL (camelCase). A section is removed once breedview implements it; the earlier ones (Persons,
invitations, transfers, record group extents, the renamed areas, contributions, times, bulk control, Person views and
maps) are in this file's history, last in full at `021f830` (`git show 021f830:docs/front-end-changes.md`), the two
after them (removing optional links with null, units as record group levels) at `7549579`, the three after those
(arrivals, inherited germplasm, moving units) at `a5c7625`, germplasm entries from units at `fd0c50d`, legal references given as files at `81961e6`, the Terms of Use at `1ae91b7`, accepting study licences at `de74a78`, the privacy notice from the API at `8f48104`, derived units at `a89ee36`, and licences of files at `b6298bc`. Where they
describe the API rather than the work, the schema's descriptions, README.md and the design notes in `docs/` have it.

## Where the front end is

breedview's master (`15f63b2`) implements every API change up to 2026-10-22, except the derivation stages (below).

**For the next API change:** add a section for it, with what breaks and the work it needs; then, in breedview,
regenerate the schema files with the API running (`node scripts/fetchGraphqlSchema.js` writes `schema.graphql`,
`possibleTypes.json` and `unionTypes.json`) and run the check script below.

## Derivation stages

A unit's derivation gives the stage the material was at when it became the unit, rather than a germplasm source type,
and deriving lets the germplasm be chosen (README, Unit).

- `UnitDerivation.sourceType` and `UnitDerivationInput.sourceType` are now `stage: DerivationStage` (UNKNOWN, SEED,
  SEEDLING, CUTTING, ROOTED_CUTTING, PLANT, IN_VITRO, PLANTLET). Breaks: every operation asking for or giving
  `sourceType` on a derivation. Work: the stage in the derive and "derived from" forms and on the unit card, with the
  enum's descriptions as help; the description's help suggests the approximate stage, or how a graft was formed.
- `unitsDeriveUnits(stage, germplasmId, copyGermplasm)`, `stage` in place of `sourceType`: `germplasmId` gives every
  new unit that germplasm; without it, `copyGermplasm` (default true) copies each source's, and false gives none. Work:
  a germplasm choice in the derive form: each unit's own, copied (the default), one for them all, or none.

## Checking the front end against the API

```bash
set -a; . instance/breedgraph.env; . instance/private.breedgraph.env; set +a
.venv/bin/python scripts/check_front_end_queries.py ../breedview/src
```

It builds the API's schema and validates every operation in the front end's `.graphql` files, with the fragments each uses, and exits with 1 if any fails.
It does not check variables, so input fields built in JavaScript (as `roleIds` was) need a search.
Rerun it after changing the front end, and after any API change, before releasing either.
