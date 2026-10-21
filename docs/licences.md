# Licences: design note

A study may name a licence for the use of its data: a legal reference whose terms people agree to before they get the
data, as everyone agrees to the Terms of Use before using BreedGraph. This note records how a licence is kept
readable, how its text is given, what identifies the text agreed to, and how agreements are kept without records.
It is not legal advice: whether agreeing in BreedGraph binds anyone is for the University's legal office.

## 1. A licence is readable by whoever reads the data by release

A study's licence is a legal reference released at least as widely as the study and every dataset of the study, so
whoever reads them by release (registered users, or everyone) can read the terms they are under, not a placeholder.
Those who read them through a controlling team make their own agreements outside BreedGraph, so a private study can
have a licence private to another team. The rule is checked as the unit of work commits, on the releases that result;
docs/read-access.md rule 10 has the details, and `scripts/check_study_licences.py` reports studies that break it.

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
they can later ask for credit for information anyone can see, such as germplasm and locations. Their draft for review
is `docs/legal/terms-of-use.md`; the API serves the published copy (`src/breedgraph/legal/terms_of_use.md`, or the file
`TERMS_OF_USE_PATH` names), read once at start-up with its SHA-256.

**The gate.** Every GraphQL operation is refused, with the error code `TERMS_NOT_ACCEPTED` (on HTTP 200), unless the
request's user has accepted the current Terms; only `termsOfUse`, `termsAccept` and introspection are open before
(`graphql_endpoint.py`, a validation rule added for such requests). REST endpoints are not gated: CSRF, email
verification and password reset links, map tiles, the workers' endpoints, and downloads, whose URLs are issued through
GraphQL. In-process GraphQL calls in tests and scripts pass no such rule.

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
accepting binds anyone is for the University's legal office (the notes in `docs/legal/terms-of-use.md`).
