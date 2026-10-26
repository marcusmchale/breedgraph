#!/bin/bash
# Runs the retention policies (unused file references, files, and expired invitations) through the API. Run on the web
# server from cron, e.g. daily, with the environment file the API runs with (docs/deployment.md):
#   30 3 * * * BREEDGRAPH_PYTHON=/opt/breedgraph/.venv/bin/python /opt/breedgraph/checkout/scripts/trigger_retention.sh /opt/breedgraph/breedgraph.env >> /var/log/breedgraph_retention.log 2>&1
#
# Cron does not load the environment, so this does: the file given, or else instance/breedgraph.env and
# instance/private.breedgraph.env, as in development. BREEDGRAPH_PYTHON selects the interpreter (default .venv/bin/python).
set -euo pipefail

ENV_FILE="${1:+$(realpath "$1")}"
cd "$(dirname "$0")/.."

set -a
if [ -n "$ENV_FILE" ]; then
    . "$ENV_FILE"
else
    . instance/breedgraph.env
    if [ -f instance/private.breedgraph.env ]; then
        . instance/private.breedgraph.env
    fi
fi
set +a

echo "$(date -Iseconds) Triggering retention"
PYTHONPATH="src${PYTHONPATH:+:${PYTHONPATH}}" "${BREEDGRAPH_PYTHON:-.venv/bin/python}" -u scripts/trigger_retention.py
