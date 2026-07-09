#!/usr/bin/env python3

import requests

from breedgraph.config import get_base_url, RETENTION_AUTH_TOKEN

import logging
logger = logging.getLogger(__name__)

BASE_URL = get_base_url()
RETENTION_URL = f"{BASE_URL}retention/run"

print("Trigger file retention")
resp = requests.post(
    f"{RETENTION_URL}?reason=scheduled",
    headers={"Authorization": f"Bearer {RETENTION_AUTH_TOKEN}"},
    timeout=300
)
resp.raise_for_status()
print("File retention response:", resp.json())
