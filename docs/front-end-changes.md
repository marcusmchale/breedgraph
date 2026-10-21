# Front-end changes

The API changes the front end (`breedview`) has yet to make, with what breaks and the work each needs. Field names are
given as in GraphQL (camelCase). A section is removed once breedview implements it; the earlier ones (Persons,
invitations, transfers, record group extents, the renamed areas, contributions, times, bulk control, Person views and
maps) are in this file's history, last in full at `021f830` (`git show 021f830:docs/front-end-changes.md`), the two
after them (removing optional links with null, units as record group levels) at `7549579`, the three after those
(arrivals, inherited germplasm, moving units) at `a5c7625`, and germplasm entries from units at `fd0c50d`. Where they
describe the API rather than the work, the schema's descriptions, README.md and the design notes in `docs/` have it.

## Where the front end is

breedview's master (`36e6bf5`) implements every API change up to 2026-10-21.

**For the next API change:** add a section for it, with what breaks and the work it needs; then, in breedview,
regenerate the schema files with the API running (`node scripts/fetchGraphqlSchema.js` writes `schema.graphql`,
`possibleTypes.json` and `unionTypes.json`) and run the check script below.

## Legal references given as files

A legal reference, such as a study's licence, can be given as a .txt, .md or .pdf file whose text is read on upload,
and every legal reference has a content hash, which acceptances of it will name (docs/licences.md). New:

- `LegalReference.textFormat: TextFormat!` (`PLAIN` or `MARKDOWN`), `contentHash` (the SHA-256 of the file, or of typed
  text; null on a placeholder) and, read from a file, its `filename`, `contentType` and `fileId` (for
  `referencesFileDownload` once it is saved).
- `referencesCreateLegalFile(reference: LegalFileReferenceInput!, controlTeamId, release)` and
  `referencesUpdateLegalFile(reference: LegalFileReferenceUpdate!)`, with the file as `file: Upload!`. The file is
  checked and read at once, so a wrong one is refused with a message; it is then saved as other files are, and the
  result is the key to follow with `referencesFileSubmission`. Without a description, the file's name is used.
- `textFormat` on `LegalReferenceInput` (`PLAIN` when omitted) and `LegalReferenceUpdate`. `LegalReferenceUpdate.text` is
  now optional: omitted or unchanged, only the description changes; new typed text replaces a file the reference was
  read from.

Nothing breaks. Work in breedview: render a legal reference's text by its format, markdown safely, with the file it was
read from, and let the legal reference form take a file.

## Checking the front end against the API

```bash
set -a; . instance/breedgraph.env; . instance/private.breedgraph.env; set +a
.venv/bin/python scripts/check_front_end_queries.py ../breedview/src
```

It builds the API's schema and validates every operation in the front end's `.graphql` files, with the fragments each uses, and exits with 1 if any fails.
It does not check variables, so input fields built in JavaScript (as `roleIds` was) need a search.
Rerun it after changing the front end, and after any API change, before releasing either.
