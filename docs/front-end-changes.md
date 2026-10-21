# Front-end changes

The API changes the front end (`breedview`) has yet to make, with what breaks and the work each needs. Field names are
given as in GraphQL (camelCase). A section is removed once breedview implements it; the earlier ones (Persons,
invitations, transfers, record group extents, the renamed areas, contributions, times, bulk control, Person views and
maps) are in this file's history, last in full at `021f830` (`git show 021f830:docs/front-end-changes.md`), the two
after them (removing optional links with null, units as record group levels) at `7549579`, the three after those
(arrivals, inherited germplasm, moving units) at `a5c7625`, germplasm entries from units at `fd0c50d`, and legal references given as files at `81961e6`. Where they
describe the API rather than the work, the schema's descriptions, README.md and the design notes in `docs/` have it.

## Where the front end is

breedview's master (`6ced55d`) implements every API change up to legal references given as files (2026-10-22).

**For the next API change:** add a section for it, with what breaks and the work it needs; then, in breedview,
regenerate the schema files with the API running (`node scripts/fetchGraphqlSchema.js` writes `schema.graphql`,
`possibleTypes.json` and `unionTypes.json`) and run the check script below.

## The Terms of Use

Everyone accepts the Terms of Use before using BreedGraph (docs/licences.md §4). **This breaks the front end**: every
GraphQL operation is refused, with errors whose `extensions.code` is `TERMS_NOT_ACCEPTED` (on HTTP 200, with no
data), until the request's user has accepted the current Terms. New:

- `termsOfUse: TermsOfUsePayload!`, open before accepting: `text` (markdown), `contentHash` and `accepted`.
- `termsAccept(contentHash: String!): BooleanPayload!`, open before accepting; refused if the Terms changed since they
  were read. It sets the acceptance cookie (`acceptances` signed out, `acceptances_<user id>` signed in), which the
  browser sends from then on.
- `accountsLogin` carries a current acceptance over from the signed-out cookie, so a visitor who accepted and then
  signs in isn't asked again.

Work in breedview: before anything else (but the privacy notice and the Terms themselves), show the Terms, rendered,
with a checkbox and Accept, calling `termsAccept` with their `contentHash`; a `/terms` page; ask again when a
`TERMS_NOT_ACCEPTED` error comes back (the Terms changed, or a signed-out acceptance lapsed); and accept the Terms in the
e2e harness (`loginAs`, `register` and the anonymous tests).

## Checking the front end against the API

```bash
set -a; . instance/breedgraph.env; . instance/private.breedgraph.env; set +a
.venv/bin/python scripts/check_front_end_queries.py ../breedview/src
```

It builds the API's schema and validates every operation in the front end's `.graphql` files, with the fragments each uses, and exits with 1 if any fails.
It does not check variables, so input fields built in JavaScript (as `roleIds` was) need a search.
Rerun it after changing the front end, and after any API change, before releasing either.
