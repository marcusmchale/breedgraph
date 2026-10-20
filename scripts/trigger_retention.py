#!/usr/bin/env python3
"""
Runs the retention policies on the web server: removing unused file references and their files, archiving or
removing files (see the archive worker), and removing expired invitations. Run from cron with scripts/trigger_retention.sh, which loads the settings.
"""
import sys

import requests

from breedgraph.config import get_base_url, RETENTION_AUTH_TOKEN

RETENTION_URL = f"{get_base_url()}retention/run"


def main() -> int:
    print("Triggering retention")
    try:
        resp = requests.post(
            f"{RETENTION_URL}?reason=scheduled",
            headers={"Authorization": f"Bearer {RETENTION_AUTH_TOKEN}"},
            timeout=300
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"Retention failed: {e}", file=sys.stderr)
        return 1
    print("Retention response:", resp.json())
    return 0


if __name__ == "__main__":
    sys.exit(main())
