#!/bin/bash
set -e

if [ $# -ne 1 ]; then
    echo "Usage: $0 <backup-filename>"
    exit 1
fi

BACKUP_FILE="$1"
BACKUP_PATH="${NEO4J_ARCHIVE_PATH/}/${BACKUP_FILE}"
TEMP_DUMP="${NEO4J_ARCHIVE_PATH}/${DATABASE_NAME}.dump"

if [ ! -f "$BACKUP_PATH" ]; then
    echo "Backup file not found:"
    echo "$BACKUP_PATH"
    exit 1
fi

echo "WARNING: This will overwrite database '${DATABASE_NAME}'."
echo "Backup:"
echo "${BACKUP_PATH}"

read -r -p "Continue? Type 'yes' to proceed: " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Cancelled."
    exit 1
fi

NEO4J_STOPPED=0

cleanup() {
    if [ "$NEO4J_STOPPED" -eq 1 ]; then
        echo "Restarting Neo4j..."
        sudo service neo4j start
    fi
    if [ -f "${TEMP_DUMP}" ]; then
        echo "Removing temporary dump file..."
        sudo -u neo4j rm -f "${TEMP_DUMP}"
    fi
}

trap cleanup EXIT

echo "Stopping Neo4j..."
sudo service neo4j stop
NEO4J_STOPPED=1

echo "Copying backup to temporary path for restoration: ${TEMP_DUMP}"
sudo -u neo4j cp ${BACKUP_PATH} ${TEMP_DUMP}

echo "Restoring backup: ${TEMP_DUMP}"
sudo -u neo4j neo4j-admin database load \
    "${DATABASE_NAME}" \
    --from-path="${NEO4J_ARCHIVE_PATH}" \
    --overwrite-destination=true

echo "Starting Neo4j..."
sudo service neo4j start
NEO4J_STOPPED=0

echo "Removing temporary dump file ${TEMP_DUMP}"
sudo -u neo4j rm ${NEO4J_ARCHIVE_PATH}/${DATABASE_NAME}.dump

# Persons erased after the backup was taken must be erased again before the database is used
ERASURE_LOG="${PERSON_ERASURE_LOG_PATH:-instance/person_erasure_log.jsonl}"
if [ -f "${ERASURE_LOG}" ]; then
    echo "Applying the Person erasure log: ${ERASURE_LOG}"
    for attempt in $(seq 1 12); do
        if "${BREEDGRAPH_PYTHON:-python3}" "$(dirname "$0")/apply_person_erasures.py" "${ERASURE_LOG}"; then
            break
        fi
        if [ "$attempt" -eq 12 ]; then
            echo "ERROR: Could not apply the Person erasure log. Apply it before using the database:"
            echo "  scripts/apply_person_erasures.py ${ERASURE_LOG}"
            exit 1
        fi
        echo "Waiting for Neo4j to accept connections..."
        sleep 5
    done
else
    echo "WARNING: No Person erasure log at ${ERASURE_LOG}."
    echo "If any Persons have been erased, restore the log from the archive server and run:"
    echo "  scripts/apply_person_erasures.py <log>"
fi

echo "Restore complete."