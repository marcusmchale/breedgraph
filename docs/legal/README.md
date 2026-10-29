# Legal texts

Drafts of BreedGraph's legal texts, each with the notes for its reviewers in a separate file:

- `privacy-notice.md`, for the University's Data Protection Officer to confirm; notes in `privacy-notice-notes.md`.
- `terms-of-use.md`, for the University's legal office to confirm; notes in `terms-of-use-notes.md`.

They describe the system as implemented: see `docs/person.md` for Person records, `docs/licences.md` for how the Terms
and study licences are accepted, and `docs/read-access.md` for who can read what. Text in [square brackets] is a fact
to fill in before publishing.

## Other deployments

The texts are written for the University's deployment. Another deployment publishes its own copies (below), and
adapts what depends on its context. One supporting a consortium, say, whose agreement already sets how its members use
and release each other's data, replaces the Terms' "Other information released beyond its team" with what the agreement
says, or refers to it, and names its own operator and contacts throughout.

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

breedview asks for consent where the API requires it since the revision of 23 October 2026, on registering and on
recording a Person (breedview `d86198a`; the change is in `docs/front-end-changes.md`'s history at `28924f0`).
