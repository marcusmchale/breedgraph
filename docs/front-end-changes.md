# Front-end changes

The API changes the front end (`breedview`) has yet to make, with what breaks and the work each needs. Field names are
given as in GraphQL (camelCase). A section is removed once breedview implements it; the earlier ones (Persons,
invitations, transfers, record group extents, the renamed areas, contributions, times, bulk control, Person views and
maps) are in this file's history, last in full at `021f830` (`git show 021f830:docs/front-end-changes.md`), the two
after them (removing optional links with null, units as record group levels) at `7549579`, the three after those
(arrivals, inherited germplasm, moving units) at `a5c7625`, germplasm entries from units at `fd0c50d`, legal references given as files at `81961e6`, the Terms of Use at `1ae91b7`, accepting study licences at `de74a78`, the privacy notice from the API at `8f48104`, derived units at `a89ee36`, licences of files at `b6298bc`, derivation stages at `2a8740d`, the ontology's public citations at `5ddb940`, adding children to several units at `4696d21`, removed ontology entries, layout locations and deleting layouts, clearing fields in updates and consent to records of people at `28924f0`, several accesses to a team in an invitation at `070eb3c`, the place search from GeoNames at `8fa9765`, a licence before release with the standard licences at `d5815a8`, scale categories on the scale and definitions that records cite at `ab85d9c`, and the observation unit by subject at `e235285`. Where they
describe the API rather than the work, the schema's descriptions, README.md and the design notes in `docs/` have it.

## Where the front end is

breedview (`4a6a9fc`) implements every API change up to 2026-10-29, except the two below.

## Team attributions

Nothing breaks. A team may set an attribution, the text to credit it by, which anyone sees with what the team
controls (docs/read-access.md, rule 9).

- **The API:** `TeamInput.attribution` and `TeamUpdate.attribution` (left out is unchanged; null or empty clears it);
  `Team.attribution`, the team's own, and `Team.inheritedAttribution`, the nearest above it in its team tree;
  `Controller.attributions`, for signed-in users; and the open query `controlsAttributions(entityLabel, entityIds)`,
  one `{ entityId, attributions }` for each id asked for, with none for an entity the user cannot read.
- **The team form** (create and edit): an Attribution field, with the inherited one as its placeholder, and a hint that
  it is public, so it shouldn't name people without their agreement.
- **Credit with the controls:** the controller badge's details and modal show "Credit: …" from
  `Controller.attributions`; visitors, who see no badge, see the credit alone where the badge would be, from
  `controlsAttributions`, asked for once per label and page where a page lists many entities.
- **The analysis summary:** the report's data table names each dataset's credit.

## The ontology's contributors

Nothing breaks. A person may choose to be named among the contributors to the ontology versions their work is in
(docs/person.md §6).

- **The API:** `peopleSetOntologyCredit(listed)`, for the user's own linked Person; `Person.ontologyCredit`, in the full
  view; and the open query `ontologyContributors(versionId)`, the name, institution and ORCID iD of each person listed
  for a version, the current one by default, in name order.
- **The profile:** in the person record's section, a choice to be listed among the ontology's contributors, saying that
  the name, institution and ORCID iD are then shown to anyone, with the versions the user's work is in.
- **The ontology page:** the version shown names its contributors, to anyone, beside its licence: everyone who
  contributes is credited together, and these are the ones who agreed to be named.

**For the next API change:** add a section for it, with what breaks and the work it needs; then, in breedview,
regenerate the schema files with the API running (`node scripts/fetchGraphqlSchema.js` writes `schema.graphql`,
`possibleTypes.json` and `unionTypes.json`) and run the check script below.

## Checking the front end against the API

```bash
set -a; . instance/breedgraph.env; . instance/private.breedgraph.env; set +a
.venv/bin/python scripts/check_front_end_queries.py ../breedview/src
```

It builds the API's schema and validates every operation in the front end's `.graphql` files, with the fragments each uses, and exits with 1 if any fails.
It does not check variables, so input fields built in JavaScript (as `roleIds` was) need a search.
Rerun it after changing the front end, and after any API change, before releasing either.
