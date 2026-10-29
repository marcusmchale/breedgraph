# Manual checks

Scripts for checks that the automated suite cannot run, because they need a running server, an external service and someone at a browser.
Pytest does not collect them. Run them directly, with the env files loaded as for the tests.

- `orcid_sandbox_link.py`: links an ORCID iD through the real ORCID sandbox, without the front end's `/orcid` page.
  The automated tests sign id_tokens with a key of their own in place of ORCID's (`utilities/orcid_tokens.py`).
  `--create-user` writes a test user to the configured database directly, so use it only on a test database.
