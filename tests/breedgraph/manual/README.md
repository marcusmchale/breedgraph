# Manual checks

Scripts for checks that the automated suite cannot run, because they need a running server, an external service and someone at a browser.
Pytest does not collect them. Run them directly, with the env files loaded as for the tests.

- `orcid_sandbox_link.py`: links an ORCID iD through the real ORCID sandbox, until the front-end `/orcid` page exists.
  The automated tests fake ORCID (`unit/adapters/test_orcid_service.py`, `e2e/people/test_orcid_api.py`).
  `--create-user` writes a test user to the configured database directly, so use it only on a test database.
