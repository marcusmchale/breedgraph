# Licences: design note

A study names a licence for the use of its data before it, or its data, is released beyond the teams that hold it: a
legal reference whose terms people agree to before they get the data, as everyone agrees to the Terms of Use before
using BreedGraph. This note records how a licence is kept
readable, how its text is given, what identifies the text agreed to, and how agreements are kept without records.
The standard licences, and the ontology's, are in §6.
It is not legal advice: whether agreeing in BreedGraph binds anyone is for the University's legal office.

## 1. Released data has a licence, readable by whoever reads the data by release

A study released beyond private, or with a dataset released beyond private, has a licence: so all study data that
leaves the teams holding it comes with terms, which its curators choose, a standard licence (§6) or their own. The files
its data cites are not held to this: a file may be another team's, cited by a private study it cannot see, and until the
study has a licence a file released beyond its team is under the Terms of Use, as other information is.

A study's licence is a legal reference released at least as widely as the study, every dataset of the study, and every
file its datasets or their records cite (a reference with a file, which holds data, §5). So whoever reads them by
release (registered users, or everyone) can read the terms they are under, not a placeholder, and can accept them
before downloading such a file even when they cannot see the dataset citing it.

**Private data.** While a study and its data are private, the teams that hold them decide who reads them, by giving read
access, and agree their own terms with those readers outside BreedGraph, in a collaboration or consortium agreement for
instance. BreedGraph asks no one who reads data through a controlling team to accept its licence (§5), so a private
study needs no licence, and can have one private to another team.

Both rules are checked as the unit of work commits, on the releases that result; docs/read-access.md rule 10 has the
details, and `scripts/check_study_licences.py` reports studies that break them.

## 2. The text of a legal reference

A legal reference's text is typed, as plain text or markdown, or read from a file when it is uploaded:

| File | Read as | Stored and served as |
|---|---|---|
| `.txt` | UTF-8 text, plain | `text/plain; charset=utf-8` |
| `.md` | UTF-8 text, markdown | `text/markdown; charset=utf-8` |
| `.pdf` | the text of its pages, plain, a blank line between pages | `application/pdf` |

- The extension decides, not the content type the client claims, and the content must match it: a PDF starts with
  `%PDF-`, and a text file is UTF-8 without NUL bytes. A byte order mark is dropped, and line endings become `\n`.
- A file is at most `LEGAL_FILE_SIZE_LIMIT` bytes (5 MB), and a PDF at most `LEGAL_FILE_PAGE_LIMIT` pages (200).
- A PDF protected by a password, or with no text (a scan), is refused: its text must then be given as a .txt or .md
  file. A PDF encrypted with an empty password, which only restricts changes, is read.
- The file is checked and read before anything is stored, so a wrong file is refused at once with a message saying why
  (`service_layer/infrastructure/legal_files.py`). It is then saved and archived as other files are, and can be
  downloaded. The text is stored on the reference, so showing it never needs the file.
- Text from a file replaces the reference's text with the file swap, once the new file is saved. Typed text replaces a
  file the reference was read from, which is deleted as replaced files are. The same text again changes nothing.

The front end renders markdown with its own small renderer, which escapes everything first and links only http, https
and mailto addresses.

## 3. The content hash

Every legal reference has a content hash: the SHA-256 of the file its text was read from, or of the typed text's UTF-8.
It names the text an acceptance agrees to. A licence changed in place gets a new hash, so those who accepted it are
asked again. Legal references written before the hash was kept were typed, so their hash is computed from their text
when they are read; nothing needed backfilling.

## 4. The Terms of Use and acceptance tokens

Everyone accepts the Terms of Use before using BreedGraph, through the website or the API, and the study licences
before their data (§5). The Terms forbid sharing accounts and acceptances, and passing data on outside its licence;
and ask for credit for what is used, naming BreedGraph and the attributions of the teams that hold it
(`controlsAttributions`), including information anyone can see, such as germplasm and locations. Their draft for review
is `docs/legal/terms-of-use.md`; the API serves the published copy (`src/breedgraph/legal/terms_of_use.md`, or the file
`TERMS_OF_USE_PATH` names), read once at start-up with its SHA-256. It serves the privacy notice the same way
(`src/breedgraph/legal/privacy_notice.md`, or the file `PRIVACY_NOTICE_PATH` names; drafted in
`docs/legal/privacy-notice.md`), as `privacyNotice`, with its hash, which an account records with the consent given
when registering; nobody accepts it as the Terms are accepted. Publishing either is in `docs/legal/README.md`.

**The gate.** Every GraphQL operation is refused, with the error code `TERMS_NOT_ACCEPTED` (on HTTP 200), unless the
request's user has accepted the current Terms; only `termsOfUse`, `termsAccept`, `privacyNotice` and introspection are
open before (`graphql_endpoint.py`, a validation rule added for such requests). REST endpoints are not gated: CSRF,
email verification and password reset links, map tiles, the workers' endpoints, and downloads, whose URLs are issued
through GraphQL. In-process GraphQL calls in tests and scripts pass no such rule.

**No records.** Nothing is stored about who accepted what. What a browser's user has accepted is one signed token
(itsdangerous, `ACCEPTANCE_SALT`) per identity, in a cookie (`service_layer/application/acceptance_tokens.py`):

| Cookie | For | Lasts |
|---|---|---|
| `acceptances` | a visitor who isn't signed in | `ACCEPTANCE_EXPIRES_ANONYMOUS` minutes (7 days) |
| `acceptances_<user id>` | a signed-in user | `ACCEPTANCE_EXPIRES_SIGNED_IN` minutes (365 days) |

- A token holds the user id (or none), the hash of the Terms accepted and, by licence id, the content hash of each
  licence accepted (§5). It counts only for its own identity: a second person signing in on the same browser inherits
  nothing, and a lapsed sign-in can't overwrite an account's token. An acceptance counts only while its text's hash is
  current, so a change to the Terms or a licence asks again.
- The lifetime is checked from the token's own time, and set as the cookie's. Each acceptance reissues the token,
  which renews it. Cookies are HttpOnly, Secure, SameSite strict, as `auth_token` is.
- Signing in copies a current Terms acceptance from the signed-out token into the account's, so nobody is asked twice
  in a row. Licences are not copied: they stay with whoever accepted them. Signing out leaves the tokens.
- A cookie holds 4 KB, so a token is kept under 3,500 bytes by dropping the least recently accepted licences, which
  are then asked for again.

**Limits.** No one person's acceptance can be revoked: a licence's owners change the licence instead, which asks
everyone again. The signed-out token can be copied to another browser; the Terms forbid it. Whether this way of
accepting binds anyone is for the University's legal office (`docs/legal/terms-of-use-notes.md`).

## 5. Accepting a study's licence

A study's data is given only to requests carrying an acceptance of its licence's current text, unless the user is
exempt (`entrypoints/fastapi/graphql/licences.py`):

| What | Without an acceptance |
|---|---|
| `Dataset.records`, `Dataset.dimensions` (its value percentiles show the values) | null, with a GraphQL error on the field (`LicenceNotAcceptedError`) |
| `analysisSubmit` | refused with `LICENCE_NOT_ACCEPTED` at `['datasetIds', i]`, checked as it is submitted, while the request's acceptances are there; the analysis runs later |
| `referencesFileDownload` for a file cited by a licensed dataset or its records | refused (`LicenceNotAcceptedError`) |

Summaries, counts, unit ids, the unit trees and places stay open, as catalogue information, and the licence itself is
readable by whoever reads the data by release (§1). Nothing changes for datasets without a licence.

- **Exempt** are those who read the dataset, or its study, through a controlling team, an affiliation rather than a
  release: the data's owners, who make their own agreements. `Dataset.licenceRequired` says whether the user must
  accept `Dataset.licence`.
- **A file counts every dataset citing it**, directly or through its records, whether the user can see the dataset or
  not: a file released more widely than the data citing it still holds that data. It opens if the user is exempt for one
  of them, or reads the file itself through a controlling team, as its owners; otherwise it needs every licence of the
  datasets citing it. §1 keeps those licences readable to whoever reads the file by release, and
  `FileDownloadState.licences` lists those still to accept, so they can be accepted before the download, without
  finding the data. The datasets themselves are not shown.
- **Download links come only from `referencesFileDownload`.** The email that tells people an archived file they asked
  for has been retrieved links to the site, not to the file, so the download is checked like any other.
- `licencesAccept(licences: [{id, contentHash}])` checks that each is a legal reference the user can read, at its
  current hash, all or none, and adds them to the identity's token, beside the Terms (§4). Keyed by licence id, a
  licence shared by many studies is one acceptance. `LegalReference.accepted` says whether the request carries an
  acceptance of the reference's current text.

## 6. Standard licences and the ontology's licence

Every deployment starts with two standard licences, seeded with the ontology's first entries
(`service_layer/application/licence_seed.py`, run by `scripts/setup_initial_data.py`, the database builds and the
test setup through `initial_data.seed_initial_data`):

| Seed key | Licence | Text |
|---|---|---|
| `cc-by-4.0` | Creative Commons Attribution 4.0 International (CC BY 4.0) | `src/breedgraph/legal/licences/cc-by-4.0.txt` |
| `cc0-1.0` | Creative Commons CC0 1.0 Universal, a public domain dedication | `src/breedgraph/legal/licences/cc0-1.0.txt` |

- Each is a legal reference with Creative Commons' legal code as its plain text, packaged unchanged (CC dedicates the
  text of its licences to the public domain), and its content hash is that of the file (§3).
- Each has **no controls**, so it is fixed: everyone can read it and cite it, as a study's licence or the ontology's,
  and no one can change it, remove it or set its release (docs/read-access.md, rule 11). It is always public, so it
  meets the release rule (§1) for any study.
- Each has a seed key, set only by seeding, which finds it again: seeding creates only what is missing.
  `scripts/seed_licences.py` seeds them into a database set up before they were.
- `referencesStandardLicences` lists them, in this order, to anyone, for licence pickers to offer first, and their
  controllers say `fixed`.

**The ontology's licence.** The ontology is shared, so its licence must be public (docs/read-access.md, rule 10). Its
first version, made by seeding, is under CC BY 4.0: the CRediT roles in it are NISO's, under CC BY 4.0
(docs/contributions.md §3), and the Terms of Use ask contributors to license what they add under it. A new version keeps
the latest version's licence unless it names another (`ontologyCommitVersion`'s `licenceId`), and takes CC BY 4.0
where the latest has none, so the ontology always has a licence (`OntologyApplicationService.commit_version`). An
ontology admin can name another public licence for a version, for a deployment whose context calls for one; entries
from CC BY 4.0 sources, and those contributed under CC BY 4.0, stay under it with their attribution whatever a later
version names, so a new licence must allow that.
