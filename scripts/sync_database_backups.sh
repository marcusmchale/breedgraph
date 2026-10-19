#!/bin/bash
# Database backup sync, run on the archive server.
#
# This is NOT the file archive worker (archive_worker, ARCHIVE_* settings), which moves uploaded files
# to archive storage. This script copies only:
#   - Neo4j database dumps, written on the web server by scripts/backup.sh, encrypted (.dump.age), and
#   - the erasure log of erased Persons and deleted accounts, which scripts/restore.sh replays after loading a dump (docs/person.md §5).
#
# Settings are read from BACKUP_SYNC_ENV (default /etc/breedgraph/backup_sync.env) if it exists,
# otherwise from the environment. See instance/backup_sync.env for an example.
#
# Cron (hourly, or at least as often as dumps are made: an erasure is at risk until the log has been copied):
#   0 * * * * /path/to/breedgraph/scripts/sync_database_backups.sh >> /var/log/breedgraph_backup_sync.log 2>&1
#
# This server needs ssh key access to BACKUP_SOURCE, and rsync on both servers.
# It never needs the encryption key: the dumps it holds can be read only with the key kept elsewhere.
set -euo pipefail

BACKUP_SYNC_ENV="${BACKUP_SYNC_ENV:-/etc/breedgraph/backup_sync.env}"
if [ -f "${BACKUP_SYNC_ENV}" ]; then
    set -a
    # shellcheck disable=SC1090
    . "${BACKUP_SYNC_ENV}"
    set +a
fi

: "${BACKUP_SOURCE:?BACKUP_SOURCE is required: ssh destination of the web server, e.g. breedgraph@web.example.org}"
: "${NEO4J_ARCHIVE_PATH:?NEO4J_ARCHIVE_PATH is required: the dump directory on the web server}"
: "${PERSON_ERASURE_LOG_PATH:?PERSON_ERASURE_LOG_PATH is required: absolute path of the erasure log on the web server}"
: "${BACKUP_DESTINATION_PATH:?BACKUP_DESTINATION_PATH is required: the directory on this server receiving the copies}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-}"

mkdir -p "${BACKUP_DESTINATION_PATH}"
echo "$(date -Iseconds) Syncing database backups from ${BACKUP_SOURCE}"

# Dumps are never changed once written, so only new ones are copied.
# One still being written is named .partial, so it is left for the next sync.
rsync -az --ignore-existing \
    --include='*.dump.age' --include='*.dump' --exclude='*' \
    "${BACKUP_SOURCE}:${NEO4J_ARCHIVE_PATH}/" \
    "${BACKUP_DESTINATION_PATH}/"

# The erasure log only grows. --append-verify adds what is beyond the end of the copy here,
# so a truncated or missing log on the web server never shortens the copy.
if ssh "${BACKUP_SOURCE}" test -f "${PERSON_ERASURE_LOG_PATH}"; then
    rsync -az --append-verify \
        "${BACKUP_SOURCE}:${PERSON_ERASURE_LOG_PATH}" \
        "${BACKUP_DESTINATION_PATH}/person_erasure_log.jsonl"
else
    echo "No erasure log on the web server yet: ${PERSON_ERASURE_LOG_PATH}"
fi

# Optionally remove old dumps here. The erasure log is never removed: it must cover every dump that could be restored.
if [ -n "${BACKUP_RETENTION_DAYS}" ]; then
    echo "Removing dumps older than ${BACKUP_RETENTION_DAYS} days"
    find "${BACKUP_DESTINATION_PATH}" -maxdepth 1 -type f \( -name '*.dump.age' -o -name '*.dump' \) \
        -mtime +"${BACKUP_RETENTION_DAYS}" -print -delete
fi

echo "$(date -Iseconds) Database backup sync complete"
