#!/bin/bash
# Loads a dump from NEO4J_ARCHIVE_PATH over DATABASE_NAME, then applies the erasure log.
# A <database>-<date>.dump.age is decrypted with the key file ENCRYPTION_IDENTITY_PATH (docs/backups.md, Encryption key);
# an unencrypted .dump, such as a test database, is loaded as it is.
set -eo pipefail

if [ $# -ne 1 ]; then
    echo "Usage: $0 <backup-filename>"
    exit 1
fi

BACKUP_FILE="$1"
BACKUP_PATH="${NEO4J_ARCHIVE_PATH}/${BACKUP_FILE}"
TEMP_DUMP="${NEO4J_ARCHIVE_PATH}/${DATABASE_NAME}.dump"

if [ ! -f "$BACKUP_PATH" ]; then
    echo "Backup file not found:"
    echo "$BACKUP_PATH"
    exit 1
fi

ENCRYPTED=0
if [[ "${BACKUP_FILE}" == *.age ]]; then
    ENCRYPTED=1
    if [ -z "${ENCRYPTION_IDENTITY_PATH}" ] || [ ! -r "${ENCRYPTION_IDENTITY_PATH}" ]; then
        echo "To restore an encrypted dump, ENCRYPTION_IDENTITY_PATH must be a key file this user can read:"
        echo "${ENCRYPTION_IDENTITY_PATH:-(not set)}"
        exit 1
    fi
    # Before anything is stopped or overwritten: a wrong key or a damaged file fails here
    echo "Checking the backup can be decrypted..."
    age --decrypt --identity "${ENCRYPTION_IDENTITY_PATH}" "${BACKUP_PATH}" > /dev/null
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

if [ "${ENCRYPTED}" -eq 1 ]; then
    echo "Restoring backup: ${BACKUP_PATH}"
    age --decrypt --identity "${ENCRYPTION_IDENTITY_PATH}" "${BACKUP_PATH}" \
        | sudo -u neo4j neo4j-admin database load \
            "${DATABASE_NAME}" \
            --from-stdin \
            --overwrite-destination=true
else
    echo "Copying backup to temporary path for restoration: ${TEMP_DUMP}"
    sudo -u neo4j cp ${BACKUP_PATH} ${TEMP_DUMP}

    echo "Restoring backup: ${TEMP_DUMP}"
    sudo -u neo4j neo4j-admin database load \
        "${DATABASE_NAME}" \
        --from-path="${NEO4J_ARCHIVE_PATH}" \
        --overwrite-destination=true
fi

echo "Starting Neo4j..."
sudo service neo4j start
NEO4J_STOPPED=0

if [ "${ENCRYPTED}" -eq 0 ]; then
    echo "Removing temporary dump file ${TEMP_DUMP}"
    sudo -u neo4j rm ${NEO4J_ARCHIVE_PATH}/${DATABASE_NAME}.dump
fi

# Persons erased and accounts deleted after the backup was taken must be erased again before the database is used
ERASURE_LOG="${PERSON_ERASURE_LOG_PATH:-instance/person_erasure_log.jsonl}"
if [ -f "${ERASURE_LOG}" ]; then
    echo "Applying the erasure log: ${ERASURE_LOG}"
    for attempt in $(seq 1 12); do
        if "${BREEDGRAPH_PYTHON:-python3}" "$(dirname "$0")/apply_erasures.py" "${ERASURE_LOG}"; then
            break
        fi
        if [ "$attempt" -eq 12 ]; then
            echo "ERROR: Could not apply the erasure log. Apply it before using the database:"
            echo "  scripts/apply_erasures.py ${ERASURE_LOG}"
            exit 1
        fi
        echo "Waiting for Neo4j to accept connections..."
        sleep 5
    done
else
    echo "WARNING: No erasure log at ${ERASURE_LOG}."
    echo "If any Persons have been erased or accounts deleted, restore the log from the archive server and run:"
    echo "  scripts/apply_erasures.py <log>"
fi

echo "Restore complete."
