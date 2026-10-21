# Licences: design note

A study may name a licence for the use of its data: a legal reference whose terms people agree to before they get the
data. This note records how a licence is kept readable, how its text is given, and what identifies the text agreed to.
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
