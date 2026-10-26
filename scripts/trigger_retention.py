#!/usr/bin/env python3
"""
Runs the retention policies on the web server: removing unused file references and their files, archiving or
removing files (see the archive worker), and removing expired invitations. Run from cron with scripts/trigger_retention.sh, which loads the settings.

It calls the API where it listens on this machine (API_URL, by default http://127.0.0.1:8000, as
instance/breedgraph.service runs it), not at the site's public address, where nginx offers the retention route to no one.
"""
import os
import sys

import httpx

from breedgraph.config import RETENTION_AUTH_TOKEN

API_URL = os.environ.get('API_URL', 'http://127.0.0.1:8000').rstrip('/')


def main() -> int:
    print("Triggering retention")
    try:
        resp = httpx.post(
            f"{API_URL}/retention/run",
            params={"reason": "scheduled"},
            headers={"Authorization": f"Bearer {RETENTION_AUTH_TOKEN}"},
            timeout=300
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        print(f"Retention failed: {e}", file=sys.stderr)
        return 1
    print("Retention response:", resp.json())
    return 0


if __name__ == "__main__":
    sys.exit(main())
