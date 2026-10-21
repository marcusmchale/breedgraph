# Front-end changes

The API changes the front end (`breedview`) has yet to make, with what breaks and the work each needs. Field names are
given as in GraphQL (camelCase). A section is removed once breedview implements it; the earlier ones (Persons,
invitations, transfers, record group extents, the renamed areas, contributions, times, bulk control, Person views and
maps) are in this file's history, last in full at `021f830` (`git show 021f830:docs/front-end-changes.md`), and the two
after them (removing optional links with null, units as record group levels) at `7549579`. Where they describe the API
rather than the work, the schema's descriptions, README.md and the design notes in `docs/` have it.

## Where the front end is

breedview's master (`4295316`) implements every API change up to 2026-10-20.

**For the next API change:** add a section for it, with what breaks and the work it needs; then, in breedview,
regenerate the schema files with the API running (`node scripts/fetchGraphqlSchema.js` writes `schema.graphql`,
`possibleTypes.json` and `unionTypes.json`) and run the check script below.

## Arrivals, and units at locations the user cannot read

Units that came to a location together from elsewhere in their unit graphs (samples sent to a lab) were found by no
query: `unitsRoots` lists only unit graph roots. New:

- `unitsArrivals(locationIds: [ID!]!, unitId: ID): UnitArrivalsPayload!`, each `UnitArrival` with `location`, `start`
  (as entered; null for the units there without a start), `unitCount`, `roots` and `unitsBySubject`. Newest first,
  undated last. With `unitId`, only the units at, below or above it: where a tree's samples went, or the arrival that
  brought a unit's parent.
- `unitsArrivalUnits(arrival: ArrivalInput!, offset: Int, limit: Int): UnitsPayload!`, a page of an arrival's units by
  name (`limit` at most 1000, default 100); `ArrivalInput { locationId, start, unitId }`, `start` as the arrival gave it.

An arrival is the readable non-root units with a position at the location from that start whose parents were not
there then: a unit is where its own position at a time puts it, else where its parent is. A unit taken from one
already there is not an arrival, and one that comes back later is a new one. `unitsRoots` and `unitsArrivals` give
nothing at a location the user cannot read.

Work in breedview: the Units page (unit graphs and arrivals at a location), links from a tree to the arrivals its
units went to, and arrivals in the dataset unit picker.

## Checking the front end against the API

```bash
set -a; . instance/breedgraph.env; . instance/private.breedgraph.env; set +a
.venv/bin/python scripts/check_front_end_queries.py ../breedview/src
```

It builds the API's schema and validates every operation in the front end's `.graphql` files, with the fragments each uses, and exits with 1 if any fails.
It does not check variables, so input fields built in JavaScript (as `roleIds` was) need a search.
Rerun it after changing the front end, and after any API change, before releasing either.
