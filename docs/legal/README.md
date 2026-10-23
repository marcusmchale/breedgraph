# Legal texts

Drafts of BreedGraph's legal texts, each with the notes for its reviewers in a separate file:

- `privacy-notice.md`, for the University's Data Protection Officer to confirm; notes in `privacy-notice-notes.md`.
- `terms-of-use.md`, for the University's legal office to confirm; notes in `terms-of-use-notes.md`.

They describe the system as implemented: see `docs/person.md` for Person records, `docs/licences.md` for how the Terms
and study licences are accepted, and `docs/read-access.md` for who can read what. Text in [square brackets] is a fact
to fill in before publishing.

## Publishing

The API serves the published copies, `src/breedgraph/legal/privacy_notice.md` and
`src/breedgraph/legal/terms_of_use.md` (or the files `PRIVACY_NOTICE_PATH` and `TERMS_OF_USE_PATH` name), to the
website and to anyone using the API; the privacy notice can be read before the Terms are accepted. To publish a draft,
once it is confirmed and complete, copy it to its published file and restart the API. Changed Terms have a new hash,
so everyone is asked to accept them again; a changed privacy notice has a new hash too, which accounts registering from
then on record with their consent.

breedview renders both with a small markdown renderer (`composables/system/markdown.js`, shared with study licences)
that handles headings, bold, italics, `-` and numbered lists, http, https and mailto links, and `---` rules only, so
the texts have no tables or nested lists.

Before publishing the revision of 23 October 2026, breedview must ask for consent where the API now requires it
(`docs/front-end-changes.md`, "Consent to records of people and to the privacy notice").
