# Front-end changes

The API changes the front end (`breedview`) has yet to make, with what breaks and the work each needs. Field names are
given as in GraphQL (camelCase). A section is removed once breedview implements it; the earlier ones (Persons,
invitations, transfers, record group extents, the renamed areas, contributions, times, bulk control, Person views and
maps) are in this file's history, last in full at `021f830` (`git show 021f830:docs/front-end-changes.md`), the two
after them (removing optional links with null, units as record group levels) at `7549579`, and the three after those
(arrivals, inherited germplasm, moving units) at `a5c7625`. Where they describe the API rather than the work, the
schema's descriptions, README.md and the design notes in `docs/` have it.

## Where the front end is

breedview's master (`239b60d`) implements every API change up to 2026-10-21.

**For the next API change:** add a section for it, with what breaks and the work it needs; then, in breedview,
regenerate the schema files with the API running (`node scripts/fetchGraphqlSchema.js` writes `schema.graphql`,
`possibleTypes.json` and `unionTypes.json`) and run the check script below.

## Germplasm entries from units

A germplasm entry can name the unit it came from, for germplasm produced by the breeding recorded here (the plant a
selection was made from, the seed of a cross), as `origin` and `time` describe germplasm sourced from elsewhere. New:

- `GermplasmEntry.unit: Unit`, through the units view: a placeholder (name `REDACTED`, no subject) where the unit is
  hidden from the user. The units of a list of entries are read at once.
- `GermplasmInput.unitId` for `germplasmCreateEntry`, and `GermplasmUpdate.unitId` for `germplasmUpdateEntry`: omitted,
  the unit is unchanged, and null removes it, as for `originId`. Linking needs read access to the unit.
- `unitsDeleteUnit` refuses a unit that germplasm came from ("Germplasm came from this unit, so it may not be
  deleted."), once the user is found to curate it.

Nothing breaks. Work in breedview: a unit picker in the germplasm form (locations opened down to their unit graphs and
arrivals, as the dataset unit picker offers them), and the unit on the germplasm card, linked to it on the Units page
where it is now, or marked as hidden.

## Checking the front end against the API

```bash
set -a; . instance/breedgraph.env; . instance/private.breedgraph.env; set +a
.venv/bin/python scripts/check_front_end_queries.py ../breedview/src
```

It builds the API's schema and validates every operation in the front end's `.graphql` files, with the fragments each uses, and exits with 1 if any fails.
It does not check variables, so input fields built in JavaScript (as `roleIds` was) need a search.
Rerun it after changing the front end, and after any API change, before releasing either.
