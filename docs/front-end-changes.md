# Front-end changes

The API changes the front end (`breedview`) has yet to make, with what breaks and the work each needs. Field names are
given as in GraphQL (camelCase). A section is removed once breedview implements it; the earlier ones (Persons,
invitations, transfers, record group extents, the renamed areas, contributions, times, bulk control, Person views and
maps) are in this file's history, last in full at `021f830` (`git show 021f830:docs/front-end-changes.md`), the two
after them (removing optional links with null, units as record group levels) at `7549579`, the three after those
(arrivals, inherited germplasm, moving units) at `a5c7625`, germplasm entries from units at `fd0c50d`, legal references given as files at `81961e6`, the Terms of Use at `1ae91b7`, accepting study licences at `de74a78`, the privacy notice from the API at `8f48104`, derived units at `a89ee36`, licences of files at `b6298bc`, derivation stages at `2a8740d`, the ontology's public citations at `5ddb940`, and adding children to several units at `4696d21`. Where they
describe the API rather than the work, the schema's descriptions, README.md and the design notes in `docs/` have it.

## Where the front end is

breedview's master (`6628435`) implements every API change up to 2026-10-23.

**For the next API change:** add a section for it, with what breaks and the work it needs; then, in breedview,
regenerate the schema files with the API running (`node scripts/fetchGraphqlSchema.js` writes `schema.graphql`,
`possibleTypes.json` and `unionTypes.json`) and run the check script below.

## Removed ontology entries

Deprecating an ontology entry now deprecates its relationships with it, and the next commit removes both (README,
Ontology). Data citing a removed entry keeps it: a dataset's concept, a unit's subject, the type of a location, layout or
grouping, a study's design and a contribution's roles resolve as before, with `phase: REMOVED` and, for a variable or
factor, its scale and categories as they stood. The ontology views treat a deprecated entry's relationships as any
deprecated relationship, so a kept entry's fields (a parent's children, a category's scales) leave out an entry from
when it is deprecated. New refusals, as errors of the payload:
- linking to a removed entry from outside the ontology, on creating it or changing to it: "Removed from the ontology,
  so nothing new can be linked to it: Subject 12 (Leaf). Choose a current entry"; and to a draft, which a commit may
  never publish: "Not yet in a committed version of the ontology, so nothing can be linked to it: ... Commit the
  version first" (pickers for data should offer the published view's entries);
- deprecating an entry a current entry is defined by: "Entries that current entries are defined by can't be
  deprecated, unless they are deprecated together: Variable 1 --[UsesScale]--> Scale 2";
- cancelling the deprecation of an entry while one it is defined by stays deprecated ("... cancel both: ..."), and
  cancelling a relationship's deprecation when it was deprecated with an entry ("... cancel their deprecation
  instead");
- adding a relationship to a deprecated entry: "Entries [2] are deprecated: relationships to them can't be added".

`ontologyRestoreEntries(ids: [ID!]!): BooleanPayload!` brings removed entries back as drafts, which the next commit
activates, keeping their ids, with the relationships removed with them whose other end is current or restored with
them. Refused for an entry that isn't removed, while another entry of its label has its name or abbreviation ("Another
LocationType is using the name ..."), and without the entries one is defined by ("... restore them with it: ...").

Nothing breaks. Work: show a removed entry where data cites it as retired (a tag on the dataset's variable, the unit's
subject, the location's or layout's type); deprecate entries several at a time in the ontology editor, so that an
entry and those it defines can go together; a Restore action for editors on removed entries in the views of earlier
versions, where an entry's `phase` is its phase now, so REMOVED for one since removed (and on a retired tag); show the
refusals as given.

## Layout locations and deleting layouts

`layoutsUpdateLayout` sets a location on the root of a layout tree only ("Only the root of a layout tree has a location,
which its layouts share"), and now does change the root's location (it refused every change before), but only while no
unit has a position in the tree: "Units are positioned in this layout tree, so its location may not change: move the
units to a layout at the new location instead". `layoutsDeleteLayout` refuses a layout units are positioned in, and a
root whose tree has any: "Units are positioned in this layout, so it may not be deleted: remove or move their positions
first". Nothing breaks: the location picker shows for roots only already. Work: show these refusals as given.

## Clearing fields in updates

An update now clears an optional field given as null, and an optional text field given as an empty or blank string
(README, Updates); a field left out is unchanged, as before. Each update input's description names its clearable
fields: program, trial and study fullname, description, practices, start and end; unit name and description; location
fullname (now in `LocationUpdate`), code (not a country's), description and address; layout name; germplasm
description, synonyms, time and reproduction; Person institution; team fullname; reference description, external id
and schema; ontology entries' abbreviation, description, synonyms, source URL and attribution, and a record group
type's default extent. Required fields, file metadata, record values and the account fields keep "null is unchanged".

What breaks: nothing sent today wipes data, as the forms send the current value of an untouched field, with one race:
the references modal edits a snapshot, and a reference given by id only (as from a dataset cell) gives a blank form if
Edit is clicked before its full read returns, which now clears its description, external id and schema. The germplasm
form sends null for every empty field, so emptying one there now clears it, as intended.

Schema changes: `TermUpdate.recordGroupTypeIds` added (term updates failed on it); `rank` removed from
`CategoryInput` and `CategoryUpdate` (ignored: a category is ordered on its scale); `datasetIds` removed from
`StudyInput` and `StudyUpdate` (ignored: a dataset is in a study, not the reverse); `LayoutUpdate`'s fields are all
optional now (a type or axes left out failed). breedview sends none of the removed fields.

Work: send null for a field that had a value and was emptied, in the forms that leave it out today (program, trial,
study, location, layout, unit, ontology description); fix the references modal race (edit the reference once read in
full, or wait for it).

## Consent to records of people and to the privacy notice

Consent is now the lawful basis for account data and Person records (docs/legal/privacy-notice.md).

- `informedAttestation` is renamed `consentAttestation`, on `PersonInput` and `Person`: the person who records someone
  confirms that they consented to the record, having been told about it and the privacy notice.
- `accountsCreateAccount` requires `privacyConsent: Boolean!`, refused unless true ("Registering needs your consent to
  the processing of your personal data, as the privacy notice describes"). The API records when it was given and the
  hash of the notice consented to, which `privacyNotice { contentHash }` now gives.

What breaks: every operation selecting `informedAttestation` (breedview's person fragment, so the people, programs,
studies, datasets and references queries that use it), the person form, and registration, which omits
`privacyConsent`. Work: rename the field in the fragment and the person form, with the checkbox reading as consent
("They agreed to be recorded, having been told about the record and the privacy notice"); on registration, word the
privacy checkbox as consent ("I consent to the processing of my personal data as the privacy notice describes") and
send `privacyConsent: true`.

## Checking the front end against the API

```bash
set -a; . instance/breedgraph.env; . instance/private.breedgraph.env; set +a
.venv/bin/python scripts/check_front_end_queries.py ../breedview/src
```

It builds the API's schema and validates every operation in the front end's `.graphql` files, with the fragments each uses, and exits with 1 if any fails.
It does not check variables, so input fields built in JavaScript (as `roleIds` was) need a search.
Rerun it after changing the front end, and after any API change, before releasing either.
