#!/bin/bash
# Runs the retention policies (files, and expired invitations) through the API. Run on the web server from cron, e.g. daily:
#   30 3 * * * /path/to/breedgraph/scripts/trigger_retention.sh >> /var/log/breedgraph_retention.log 2>&1
#
# Cron does not load the env files, so this does: instance/breedgraph.env and instance/private.breedgraph.env.
# BREEDGRAPH_PYTHON selects the interpreter (default .venv/bin/python).
set -euo pipefail

cd "$(dirname "$0")/.."

set -a
. instance/breedgraph.env
if [ -f instance/private.breedgraph.env ]; then
    . instance/private.breedgraph.env
fi
set +a

echo "$(date -Iseconds) Triggering retention"
PYTHONPATH="src${PYTHONPATH:+:${PYTHONPATH}}" "${BREEDGRAPH_PYTHON:-.venv/bin/python}" -u scripts/trigger_retention.py
