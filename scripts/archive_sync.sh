#!/bin/bash
# Run on the archive server, e.g. hourly from cron:
#   0 * * * * /path/to/breedgraph/scripts/archive_sync.sh >> /var/log/breedgraph_archive_sync.log 2>&1
#
# Copies new database dumps from the web server, and the Person erasure log.
# Copy the log at least as often as dumps are made: an erasure on the web server
# is at risk until the log has been copied off it.
#
# Required:
#   ARCHIVE_SOURCE              ssh destination of the web server, e.g. breedgraph@web.example.org
#   NEO4J_ARCHIVE_PATH          dump directory on the web server
#   PERSON_ERASURE_LOG_PATH     erasure log on the web server (absolute path)
#   ARCHIVE_DESTINATION_PATH    directory on this server receiving the copies
set -e

: "${ARCHIVE_SOURCE:?ARCHIVE_SOURCE is required}"
: "${NEO4J_ARCHIVE_PATH:?NEO4J_ARCHIVE_PATH is required}"
: "${PERSON_ERASURE_LOG_PATH:?PERSON_ERASURE_LOG_PATH is required}"
: "${ARCHIVE_DESTINATION_PATH:?ARCHIVE_DESTINATION_PATH is required}"

mkdir -p "${ARCHIVE_DESTINATION_PATH}"
echo "$(date -Iseconds) Syncing from ${ARCHIVE_SOURCE}"

# Dumps are never changed once written, so only new ones are copied
rsync -az --ignore-existing \
    --include='*.dump' --exclude='*' \
    "${ARCHIVE_SOURCE}:${NEO4J_ARCHIVE_PATH}/" \
    "${ARCHIVE_DESTINATION_PATH}/"

# The erasure log only grows. --append-verify adds what is beyond the end of the copy here,
# so a truncated or missing log on the web server never shortens the archived copy.
if ssh "${ARCHIVE_SOURCE}" test -f "${PERSON_ERASURE_LOG_PATH}"; then
    rsync -az --append-verify \
        "${ARCHIVE_SOURCE}:${PERSON_ERASURE_LOG_PATH}" \
        "${ARCHIVE_DESTINATION_PATH}/person_erasure_log.jsonl"
else
    echo "No erasure log on the web server yet: ${PERSON_ERASURE_LOG_PATH}"
fi

echo "$(date -Iseconds) Sync complete"
